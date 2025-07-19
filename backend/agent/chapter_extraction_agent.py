"""
Chapter-based EWA Extraction Agent

This agent handles extraction from individual document chapters for improved
reliability and accuracy in the two-model workflow.
"""

import json
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass

from agent.ewa_agent import EWAAgent
from utils.document_chunker import DocumentChunk


@dataclass
class ChapterExtractionResult:
    """Result of extracting from a single chapter"""
    chapter_title: str
    chapter_number: int
    extraction_json: Dict[str, Any]
    success: bool = True
    error_message: Optional[str] = None
    processing_time: float = 0.0
    token_usage: Optional[Dict[str, int]] = None


class ChapterExtractionAgent:
    """
    Agent specialized for extracting structured data from individual EWA document chapters.
    
    This agent uses chapter-specific prompts and processing to improve extraction
    reliability and accuracy compared to processing entire documents at once.
    """
    
    def __init__(self, client, model: str):
        """
        Initialize the chapter extraction agent.
        
        Args:
            client: Azure OpenAI client
            model: Model name to use for extraction
        """
        import os
        self.client = client
        # Always use env var for fast model, fallback to provided model
        self.model = os.getenv("AZURE_OPENAI_FAST_MODEL", model)
        
        # Chapter-specific prompt template
        self.chapter_prompt = self._create_chapter_prompt()
        
        # Initialize the base EWA agent for schema validation
        self.base_agent = EWAAgent(client=client, model=self.model)
    
    def _create_chapter_prompt(self) -> str:
        """Load the chapter extraction prompt from an external .md file."""
        import os
        prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts", "chapter_extraction_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    async def extract_from_chapter(self, chunk: DocumentChunk) -> ChapterExtractionResult:
        """
        Extract structured information from a single document chapter.
        
        Args:
            chunk: DocumentChunk containing the chapter content
            
        Returns:
            ChapterExtractionResult with extraction results
        """
        import time
        start_time = time.time()
        
        try:
            # Prepare chapter-specific prompt
            chapter_prompt = self.chapter_prompt.format(
                chapter_title=chunk.chapter_title,
                chapter_number=chunk.chapter_number
            )
            
            # Create a temporary agent with chapter-specific prompt
            chapter_agent = EWAAgent(
                client=self.client,
                model=self.model,
                summary_prompt=chapter_prompt
            )
            
            # Extract from the chapter
            print(f"[CHAPTER EXTRACTION] Processing chapter {chunk.chapter_number}: {chunk.chapter_title}")
            print(f"[CHAPTER EXTRACTION] Chapter has {chunk.word_count} words, tables: {chunk.has_tables}, metrics: {chunk.has_metrics}")
            
            extraction_json = await chapter_agent.run(chunk.content)
            
            # Add chapter metadata to the extraction
            if isinstance(extraction_json, dict):
                extraction_json['chapter_metadata'] = {
                    'chapter_title': chunk.chapter_title,
                    'chapter_number': chunk.chapter_number,
                    'word_count': chunk.word_count,
                    'has_tables': chunk.has_tables,
                    'has_metrics': chunk.has_metrics
                }
            
            processing_time = time.time() - start_time
            
            return ChapterExtractionResult(
                chapter_title=chunk.chapter_title,
                chapter_number=chunk.chapter_number,
                extraction_json=extraction_json,
                success=True,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_message = f"Error extracting from chapter '{chunk.chapter_title}': {str(e)}"
            print(f"[CHAPTER EXTRACTION ERROR] {error_message}")
            
            return ChapterExtractionResult(
                chapter_title=chunk.chapter_title,
                chapter_number=chunk.chapter_number,
                extraction_json={},
                success=False,
                error_message=error_message,
                processing_time=processing_time
            )
    
    async def extract_from_chapters(self, chunks: list[DocumentChunk]) -> list[ChapterExtractionResult]:
        """
        Extract from multiple chapters concurrently.
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            List of ChapterExtractionResult objects
        """
        print(f"[CHAPTER EXTRACTION] Starting extraction from {len(chunks)} chapters")
        
        # Create extraction tasks
        tasks = [
            self.extract_from_chapter(chunk) 
            for chunk in chunks
        ]
        
        # Execute extractions concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ChapterExtractionResult(
                    chapter_title=chunks[i].chapter_title,
                    chapter_number=chunks[i].chapter_number,
                    extraction_json={},
                    success=False,
                    error_message=str(result)
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        # Log summary
        successful = sum(1 for r in final_results if r.success)
        failed = len(final_results) - successful
        total_time = sum(r.processing_time for r in final_results)
        
        print(f"[CHAPTER EXTRACTION] Completed: {successful} successful, {failed} failed, {total_time:.2f}s total")
        
        return final_results
    
    def get_extraction_summary(self, results: list[ChapterExtractionResult]) -> Dict[str, Any]:
        """Get a summary of extraction results."""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        return {
            "total_chapters": len(results),
            "successful_extractions": len(successful),
            "failed_extractions": len(failed),
            "success_rate": f"{(len(successful) / len(results) * 100):.1f}%" if results else "0%",
            "average_processing_time": sum(r.processing_time for r in results) / len(results) if results else 0,
            "total_processing_time": sum(r.processing_time for r in results),
            "successful_chapters": [r.chapter_title for r in successful],
            "failed_chapters": [r.chapter_title for r in failed],
            "chapters_with_errors": [
                {"chapter": r.chapter_title, "error": r.error_message} 
                for r in failed
            ]
        }
