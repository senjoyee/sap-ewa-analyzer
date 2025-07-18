"""
Document Chunking Utilities for EWA Analysis

This module provides utilities for splitting large EWA documents into manageable chapters
for improved extraction reliability and accuracy.
"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    """Represents a chunk of a document with metadata"""
    chapter_title: str
    content: str
    chapter_number: int
    start_line: int
    end_line: int
    word_count: int
    has_tables: bool = False
    has_metrics: bool = False


class DocumentChunker:
    """
    Splits EWA documents into logical chapters for chapter-by-chapter processing.
    
    This class intelligently identifies chapter boundaries, preserves context,
    and handles edge cases like tables spanning multiple sections.
    """
    
    def __init__(self, min_chunk_size: int = 200, max_chunk_size: int = 8000):
        """
        Initialize the document chunker.
        
        Args:
            min_chunk_size: Minimum number of words per chunk
            max_chunk_size: Maximum number of words per chunk
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        
        # Patterns to identify chapter boundaries
        self.chapter_patterns = [
            r'^# (.+)$',           # Main headings
            r'^## (.+)$',          # Sub headings
            r'^### (.+)$',         # Sub-sub headings
            r'^\d+\.\s+(.+)$',     # Numbered sections
            r'^[A-Z][A-Z ]+:',     # All caps sections
        ]
        
        # Patterns to identify important content
        self.metric_patterns = [
            r'\d+\.\d+\s*(ms|seconds?|minutes?|hours?|%|MB|GB|TB)',
            r'\d+\s*(ms|seconds?|minutes?|hours?|%|MB|GB|TB)',
            r'Response Time:\s*\d+',
            r'CPU:\s*\d+',
            r'Memory:\s*\d+',
        ]
        
        self.table_patterns = [
            r'\|.*\|',  # Table rows
            r'^\s*\+[-=]+\+',  # Table borders
            r'^\s*[-=]{3,}',   # Horizontal separators
        ]
    
    def chunk_document(self, markdown_content: str) -> List[DocumentChunk]:
        """
        Split a markdown document into logical chapters.
        
        Args:
            markdown_content: The full markdown content to chunk
            
        Returns:
            List of DocumentChunk objects
        """
        lines = markdown_content.split('\n')
        chunks = []
        current_chunk_lines = []
        current_chapter = "Introduction"
        chapter_number = 0
        start_line = 0
        
        for i, line in enumerate(lines):
            # Check if this line is a chapter boundary
            chapter_match = self._is_chapter_boundary(line)
            
            if chapter_match:
                # Save the previous chunk if it has content
                if current_chunk_lines:
                    chunk = self._create_chunk(
                        current_chapter, 
                        current_chunk_lines, 
                        chapter_number,
                        start_line, 
                        i - 1
                    )
                    if chunk:
                        chunks.append(chunk)
                
                # Start new chunk
                current_chapter = chapter_match
                chapter_number += 1
                current_chunk_lines = [line]
                start_line = i
            else:
                current_chunk_lines.append(line)
        
        # Don't forget the last chunk
        if current_chunk_lines:
            chunk = self._create_chunk(
                current_chapter, 
                current_chunk_lines, 
                chapter_number,
                start_line, 
                len(lines) - 1
            )
            if chunk:
                chunks.append(chunk)
        
        # Post-process chunks to handle size constraints
        return self._optimize_chunks(chunks)
    
    def _is_chapter_boundary(self, line: str) -> str:
        """Check if a line represents a chapter boundary and return the title."""
        line = line.strip()
        
        for pattern in self.chapter_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                # Extract the title from the match
                if match.groups():
                    return match.group(1).strip()
                else:
                    return line.strip()
        
        return None
    
    def _create_chunk(self, title: str, lines: List[str], chapter_num: int, 
                     start_line: int, end_line: int) -> DocumentChunk:
        """Create a DocumentChunk from lines."""
        content = '\n'.join(lines)
        word_count = len(content.split())
        
        # Skip very small chunks
        if word_count < self.min_chunk_size:
            return None
        
        # Detect content characteristics
        has_tables = any(re.search(pattern, content, re.MULTILINE) 
                        for pattern in self.table_patterns)
        has_metrics = any(re.search(pattern, content, re.IGNORECASE) 
                         for pattern in self.metric_patterns)
        
        return DocumentChunk(
            chapter_title=title,
            content=content,
            chapter_number=chapter_num,
            start_line=start_line,
            end_line=end_line,
            word_count=word_count,
            has_tables=has_tables,
            has_metrics=has_metrics
        )
    
    def _optimize_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Optimize chunk sizes by merging small chunks or splitting large ones.
        
        Args:
            chunks: List of initial chunks
            
        Returns:
            Optimized list of chunks
        """
        optimized = []
        i = 0
        
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # If chunk is too large, try to split it
            if current_chunk.word_count > self.max_chunk_size:
                split_chunks = self._split_large_chunk(current_chunk)
                optimized.extend(split_chunks)
            
            # If chunk is too small, try to merge with next
            elif (i + 1 < len(chunks) and 
                  current_chunk.word_count < self.min_chunk_size and
                  chunks[i + 1].word_count < self.max_chunk_size):
                
                merged_chunk = self._merge_chunks(current_chunk, chunks[i + 1])
                if merged_chunk.word_count <= self.max_chunk_size:
                    optimized.append(merged_chunk)
                    i += 1  # Skip next chunk since it's merged
                else:
                    optimized.append(current_chunk)
            else:
                optimized.append(current_chunk)
            
            i += 1
        
        return optimized
    
    def _split_large_chunk(self, chunk: DocumentChunk) -> List[DocumentChunk]:
        """Split a large chunk into smaller ones."""
        lines = chunk.content.split('\n')
        target_lines_per_chunk = len(lines) // 2
        
        # Try to find a good split point (prefer section boundaries)
        split_point = target_lines_per_chunk
        
        # Look for a good split point near the target
        for i in range(max(1, target_lines_per_chunk - 10), 
                      min(len(lines) - 1, target_lines_per_chunk + 10)):
            if self._is_chapter_boundary(lines[i]):
                split_point = i
                break
        
        # Create two chunks
        chunk1_lines = lines[:split_point]
        chunk2_lines = lines[split_point:]
        
        chunk1 = DocumentChunk(
            chapter_title=chunk.chapter_title,
            content='\n'.join(chunk1_lines),
            chapter_number=chunk.chapter_number,
            start_line=chunk.start_line,
            end_line=chunk.start_line + len(chunk1_lines) - 1,
            word_count=len('\n'.join(chunk1_lines).split()),
            has_tables=chunk.has_tables,
            has_metrics=chunk.has_metrics
        )
        
        chunk2 = DocumentChunk(
            chapter_title=f"{chunk.chapter_title} (continued)",
            content='\n'.join(chunk2_lines),
            chapter_number=chunk.chapter_number,
            start_line=chunk.start_line + len(chunk1_lines),
            end_line=chunk.end_line,
            word_count=len('\n'.join(chunk2_lines).split()),
            has_tables=chunk.has_tables,
            has_metrics=chunk.has_metrics
        )
        
        return [chunk1, chunk2]
    
    def _merge_chunks(self, chunk1: DocumentChunk, chunk2: DocumentChunk) -> DocumentChunk:
        """Merge two adjacent chunks."""
        merged_content = chunk1.content + '\n\n' + chunk2.content
        
        return DocumentChunk(
            chapter_title=f"{chunk1.chapter_title} & {chunk2.chapter_title}",
            content=merged_content,
            chapter_number=chunk1.chapter_number,
            start_line=chunk1.start_line,
            end_line=chunk2.end_line,
            word_count=len(merged_content.split()),
            has_tables=chunk1.has_tables or chunk2.has_tables,
            has_metrics=chunk1.has_metrics or chunk2.has_metrics
        )
    
    def get_chunking_summary(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """Get a summary of the chunking results."""
        total_words = sum(chunk.word_count for chunk in chunks)
        chunks_with_tables = sum(1 for chunk in chunks if chunk.has_tables)
        chunks_with_metrics = sum(1 for chunk in chunks if chunk.has_metrics)
        
        return {
            "total_chunks": len(chunks),
            "total_words": total_words,
            "average_words_per_chunk": total_words // len(chunks) if chunks else 0,
            "chunks_with_tables": chunks_with_tables,
            "chunks_with_metrics": chunks_with_metrics,
            "chapter_titles": [chunk.chapter_title for chunk in chunks]
        }
