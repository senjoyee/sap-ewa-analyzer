"""
Test script for chapter-by-chapter analysis workflow.

Usage:
    python -m dev_tests.chapter_workflow_test --blob-name EWA_Report.pdf

This script tests the new chapter-by-chapter workflow by:
1. Loading a PDF from Azure Blob Storage
2. Running chapter enumeration
3. Analyzing each chapter
4. Merging results
5. Comparing with traditional single-pass analysis (optional)
"""

import asyncio
import sys
import os
import argparse
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow_orchestrator import ewa_orchestrator
from dotenv import load_dotenv

load_dotenv()


async def test_chapter_enumeration(blob_name: str):
    """Test chapter enumeration only."""
    print("\n" + "="*80)
    print("TEST: Chapter Enumeration")
    print("="*80)
    
    try:
        # Download PDF
        pdf_data = await ewa_orchestrator.download_pdf_from_blob(blob_name)
        print(f"✓ Downloaded PDF: {len(pdf_data)} bytes")
        
        # Create agent
        from agent.ewa_agent import EWAAgent
        agent = ewa_orchestrator._create_agent(
            os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1"),
            None
        )
        
        # Enumerate chapters
        print("\nEnumerating chapters...")
        result = await agent.enumerate_chapters(pdf_data)
        
        chapters = result.get("chapters", [])
        total_pages = result.get("total_pages", 0)
        
        print(f"\n✓ Found {len(chapters)} chapters across {total_pages} pages:")
        for chapter in chapters:
            ch_id = chapter.get("chapter_id", "?")
            title = chapter.get("title", "Unknown")
            start = chapter.get("start_page", "?")
            end = chapter.get("end_page", "?")
            print(f"  {ch_id}: {title} (pages {start}-{end})")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Chapter enumeration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_chapter_analysis(blob_name: str, chapter_enum_result: dict):
    """Test analyzing a single chapter."""
    print("\n" + "="*80)
    print("TEST: Single Chapter Analysis")
    print("="*80)
    
    try:
        chapters = chapter_enum_result.get("chapters", [])
        if not chapters:
            print("✗ No chapters to analyze")
            return None
        
        # Pick the first chapter
        test_chapter = chapters[0]
        print(f"\nTesting with: {test_chapter.get('chapter_id')} - {test_chapter.get('title')}")
        
        # Download PDF
        pdf_data = await ewa_orchestrator.download_pdf_from_blob(blob_name)
        
        # Create agent
        from agent.ewa_agent import EWAAgent
        agent = ewa_orchestrator._create_agent(
            os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1"),
            None
        )
        
        # Analyze chapter
        print("\nAnalyzing chapter...")
        result = await agent.analyze_chapter(test_chapter, pdf_data)
        
        findings = result.get("key_findings", [])
        recs = result.get("recommendations", [])
        positive = result.get("positive_findings", [])
        
        print(f"\n✓ Chapter analysis complete:")
        print(f"  - {len(findings)} key findings")
        print(f"  - {len(recs)} recommendations")
        print(f"  - {len(positive)} positive findings")
        
        if findings:
            print("\n  Sample finding:")
            print(f"    Area: {findings[0].get('area', 'N/A')}")
            print(f"    Severity: {findings[0].get('severity', 'N/A')}")
            print(f"    Finding: {findings[0].get('finding', 'N/A')[:100]}...")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Chapter analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_full_chapter_workflow(blob_name: str):
    """Test the complete chapter-by-chapter workflow."""
    print("\n" + "="*80)
    print("TEST: Complete Chapter-by-Chapter Workflow")
    print("="*80)
    
    try:
        start_time = datetime.now()
        
        result = await ewa_orchestrator.execute_workflow(
            blob_name,
            skip_markdown=True,
            chapter_by_chapter=True
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if result.get("success"):
            print(f"\n✓ Workflow completed successfully in {duration:.1f} seconds")
            
            # Display summary
            summary_json = result.get("summary_json", {})
            chapters_reviewed = summary_json.get("Chapters Reviewed", [])
            key_findings = summary_json.get("Key Findings", [])
            recommendations = summary_json.get("Recommendations", [])
            
            print(f"\n  Chapters reviewed: {len(chapters_reviewed)}")
            for chapter in chapters_reviewed[:5]:
                print(f"    - {chapter}")
            if len(chapters_reviewed) > 5:
                print(f"    ... and {len(chapters_reviewed) - 5} more")
            
            print(f"\n  Key findings: {len(key_findings)}")
            print(f"  Recommendations: {len(recommendations)}")
            
            # Show finding distribution by severity
            severity_count = {}
            for finding in key_findings:
                sev = finding.get("Severity", "unknown")
                severity_count[sev] = severity_count.get(sev, 0) + 1
            
            print(f"\n  Findings by severity:")
            for sev, count in sorted(severity_count.items()):
                print(f"    {sev.capitalize()}: {count}")
            
            return result
        else:
            print(f"\n✗ Workflow failed: {result.get('message', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"\n✗ Workflow error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def compare_workflows(blob_name: str):
    """Compare chapter-by-chapter vs traditional workflow."""
    print("\n" + "="*80)
    print("TEST: Workflow Comparison")
    print("="*80)
    
    print("\n1. Running CHAPTER-BY-CHAPTER workflow...")
    chapter_result = await ewa_orchestrator.execute_workflow(
        blob_name,
        skip_markdown=True,
        chapter_by_chapter=True
    )
    
    print("\n2. Running TRADITIONAL workflow...")
    traditional_result = await ewa_orchestrator.execute_workflow(
        blob_name,
        skip_markdown=True,
        chapter_by_chapter=False
    )
    
    # Compare results
    if chapter_result.get("success") and traditional_result.get("success"):
        ch_findings = len(chapter_result.get("summary_json", {}).get("Key Findings", []))
        tr_findings = len(traditional_result.get("summary_json", {}).get("Key Findings", []))
        
        print(f"\n✓ Comparison complete:")
        print(f"  Chapter-by-chapter: {ch_findings} findings")
        print(f"  Traditional: {tr_findings} findings")
        print(f"  Difference: {abs(ch_findings - tr_findings)} findings")
        
        if ch_findings > tr_findings:
            print(f"\n  Chapter-by-chapter found {ch_findings - tr_findings} MORE findings")
        elif tr_findings > ch_findings:
            print(f"\n  Traditional found {tr_findings - ch_findings} MORE findings")
        else:
            print(f"\n  Both workflows found the same number of findings")
    else:
        print("\n✗ One or both workflows failed, cannot compare")


async def main():
    parser = argparse.ArgumentParser(description="Test chapter-by-chapter workflow")
    parser.add_argument("--blob-name", required=True, help="Name of the PDF blob to analyze")
    parser.add_argument("--test", choices=["enum", "chapter", "full", "compare", "all"], 
                       default="full", help="Which test to run")
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"Chapter-by-Chapter Workflow Test")
    print(f"{'='*80}")
    print(f"Blob: {args.blob_name}")
    print(f"Test: {args.test}")
    print(f"{'='*80}")
    
    if args.test in ["enum", "all"]:
        enum_result = await test_chapter_enumeration(args.blob_name)
        if args.test == "enum":
            return
    else:
        enum_result = None
    
    if args.test in ["chapter", "all"] and enum_result:
        await test_chapter_analysis(args.blob_name, enum_result)
        if args.test == "chapter":
            return
    
    if args.test in ["full", "all"]:
        await test_full_chapter_workflow(args.blob_name)
    
    if args.test == "compare":
        await compare_workflows(args.blob_name)
    
    print(f"\n{'='*80}")
    print("Test complete")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
