#!/usr/bin/env python3
"""
EPUB/PDF Normalizer for Kindle-compatible eBooks
Removes duplicates, blank pages, normalizes formatting, and ensures KDP compliance.
"""

import os
import sys
import hashlib
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Set
import zipfile
import tempfile
import shutil

from ebooklib import epub
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from PIL import Image
from rapidfuzz import fuzz
import io


class EPUBNormalizer:
    def __init__(self, input_path: str, output_dir: str = "output"):
        self.input_path = input_path
        self.output_dir = output_dir
        self.log = []
        self.removed_duplicates = 0
        self.removed_blanks = 0
        
    def log_message(self, msg: str):
        """Add message to processing log"""
        print(f"[LOG] {msg}")
        self.log.append(msg)
    
    def is_blank_page(self, text: str, html: str = "") -> bool:
        """Determine if page is blank based on content"""
        clean_text = re.sub(r'\s+', '', text)
        if len(clean_text) < 10:
            return True
        # Check if only whitespace or minimal content
        if len(text.strip()) < 10:
            return True
        return False
    
    def compute_text_hash(self, text: str) -> str:
        """Compute normalized hash of text content"""
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def are_similar(self, text1: str, text2: str, threshold: float = 95.0) -> bool:
        """Check if two texts are similar using fuzzy matching"""
        if not text1 or not text2:
            return False
        ratio = fuzz.ratio(text1, text2)
        return ratio >= threshold
    
    def pdf_to_html_chapters(self, pdf_path: str) -> List[Tuple[str, str]]:
        """Convert PDF to structured HTML chapters"""
        self.log_message(f"Converting PDF: {pdf_path}")
        doc = fitz.open(pdf_path)
        chapters = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Skip blank pages
            if self.is_blank_page(text):
                self.removed_blanks += 1
                continue
            
            # Extract text with basic structure
            blocks = page.get_text("dict")["blocks"]
            html_content = self._blocks_to_html(blocks, text)
            
            title = f"Page {page_num + 1}"
            chapters.append((title, html_content))
        
        doc.close()
        self.log_message(f"Extracted {len(chapters)} pages from PDF")
        return chapters
    
    def _blocks_to_html(self, blocks: List, fallback_text: str) -> str:
        """Convert PDF blocks to HTML"""
        html_parts = []
        
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        size = span.get("size", 12)
                        
                        # Detect headings by font size
                        if size > 16:
                            line_text += f"<h2>{text}</h2>"
                        elif size > 14:
                            line_text += f"<h3>{text}</h3>"
                        else:
                            line_text += text + " "
                    
                    if line_text.strip():
                        if not line_text.startswith("<h"):
                            html_parts.append(f"<p>{line_text.strip()}</p>")
                        else:
                            html_parts.append(line_text)
        
        if not html_parts:
            # Fallback to plain text
            paragraphs = fallback_text.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    html_parts.append(f"<p>{para.strip()}</p>")
        
        return "\n".join(html_parts)
    
    def extract_epub_chapters(self, epub_path: str) -> List[Tuple[str, str, str]]:
        """Extract chapters from existing EPUB"""
        self.log_message(f"Reading EPUB: {epub_path}")
        book = epub.read_epub(epub_path)
        chapters = []
        
        for item in book.get_items():
            if item.get_type() == 9:  # XHTML content
                content = item.get_content().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'lxml')
                
                # Extract text for analysis
                text = soup.get_text()
                
                # Skip blank pages
                if self.is_blank_page(text, content):
                    self.removed_blanks += 1
                    continue
                
                # Extract title from first heading or use filename
                title = None
                for tag in ['h1', 'h2', 'h3', 'title']:
                    heading = soup.find(tag)
                    if heading:
                        title = heading.get_text().strip()
                        break
                
                if not title:
                    title = item.get_name()
                
                chapters.append((title, content, text))
        
        self.log_message(f"Extracted {len(chapters)} chapters from EPUB")
        return chapters
    
    def deduplicate_chapters(self, chapters: List[Tuple]) -> List[Tuple]:
        """Remove duplicate chapters based on content similarity"""
        if not chapters:
            return chapters
        
        unique_chapters = []
        seen_hashes = set()
        seen_texts = []
        
        for chapter in chapters:
            # Handle both 2-tuple (title, html) and 3-tuple (title, html, text)
            if len(chapter) == 3:
                title, html, text = chapter
            else:
                title, html = chapter
                soup = BeautifulSoup(html, 'lxml')
                text = soup.get_text()
            
            # Check hash-based duplicate
            text_hash = self.compute_text_hash(text)
            if text_hash in seen_hashes:
                self.removed_duplicates += 1
                self.log_message(f"Removed duplicate (hash): {title}")
                continue
            
            # Check similarity-based duplicate
            is_duplicate = False
            for seen_text in seen_texts:
                if self.are_similar(text, seen_text, threshold=95.0):
                    self.removed_duplicates += 1
                    self.log_message(f"Removed duplicate (similarity): {title}")
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_hashes.add(text_hash)
                seen_texts.append(text)
                unique_chapters.append(chapter)
        
        self.log_message(f"Kept {len(unique_chapters)} unique chapters")
        return unique_chapters
    
    def normalize_html(self, html: str) -> str:
        """Normalize HTML content with clean structure"""
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove existing style attributes
        for tag in soup.find_all(True):
            if tag.has_attr('style'):
                del tag['style']
            # Remove inline font tags
            if tag.name in ['font', 'center']:
                tag.unwrap()
        
        # Normalize line breaks
        for br in soup.find_all('br'):
            # Multiple br tags become paragraph breaks
            if br.next_sibling and br.next_sibling.name == 'br':
                br.decompose()
        
        # Ensure proper paragraph structure
        body = soup.find('body')
        if body:
            content = str(body)
        else:
            content = str(soup)
        
        # Clean up excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        return content
    
    def create_minimal_css(self) -> str:
        """Create minimal Kindle-compatible CSS"""
        return """
body {
    font-family: serif;
    line-height: 1.5;
    margin: 0;
    padding: 0;
}

p {
    margin: 0 0 1em 0;
    text-indent: 1.5em;
    text-align: justify;
}

h1, h2, h3, h4, h5, h6 {
    font-weight: bold;
    margin: 1.5em 0 0.5em 0;
    text-align: left;
    text-indent: 0;
}

h1 { font-size: 1.8em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.3em; }

em, i { font-style: italic; }
strong, b { font-weight: bold; }

.chapter-title {
    margin-top: 2em;
    margin-bottom: 1em;
}
""".strip()
    
    def build_epub(self, chapters: List[Tuple], metadata: dict) -> epub.EpubBook:
        """Build clean EPUB from chapters"""
        book = epub.EpubBook()
        
        # Set metadata
        book.set_identifier(metadata.get('identifier', str(uuid.uuid4())))
        book.set_title(metadata.get('title', 'Untitled'))
        book.set_language(metadata.get('language', 'en'))
        book.add_author(metadata.get('author', 'Unknown'))
        
        # Add optional metadata
        if 'publisher' in metadata:
            book.add_metadata('DC', 'publisher', metadata['publisher'])
        if 'date' in metadata:
            book.add_metadata('DC', 'date', metadata['date'])
        
        # Create CSS
        css = epub.EpubItem(
            uid="style",
            file_name="style.css",
            media_type="text/css",
            content=self.create_minimal_css()
        )
        book.add_item(css)
        
        # Create chapters
        epub_chapters = []
        spine = ['nav']
        
        for idx, chapter_data in enumerate(chapters):
            # Handle both 2-tuple and 3-tuple
            if len(chapter_data) == 3:
                title, html, _ = chapter_data
            else:
                title, html = chapter_data
            
            # Normalize HTML
            normalized_html = self.normalize_html(html)
            
            # Create chapter
            chapter = epub.EpubHtml(
                title=title,
                file_name=f'chapter_{idx + 1}.xhtml',
                lang=metadata.get('language', 'en')
            )
            chapter.content = normalized_html
            chapter.add_item(css)
            
            book.add_item(chapter)
            epub_chapters.append(chapter)
            spine.append(chapter)
        
        # Create TOC
        book.toc = tuple(epub_chapters)
        
        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Set spine
        book.spine = spine
        
        return book
    
    def extract_metadata(self, input_path: str) -> dict:
        """Extract or create metadata for the book"""
        metadata = {
            'identifier': str(uuid.uuid4()),
            'language': 'en',
            'publisher': 'Self-published',
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Try to extract from EPUB
        if input_path.lower().endswith('.epub'):
            try:
                book = epub.read_epub(input_path)
                metadata['title'] = book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else 'Untitled'
                metadata['author'] = book.get_metadata('DC', 'creator')[0][0] if book.get_metadata('DC', 'creator') else 'Unknown'
                
                lang = book.get_metadata('DC', 'language')
                if lang:
                    metadata['language'] = lang[0][0]
                
                pub = book.get_metadata('DC', 'publisher')
                if pub:
                    metadata['publisher'] = pub[0][0]
                    
            except Exception as e:
                self.log_message(f"Could not extract metadata: {e}")
                metadata['title'] = Path(input_path).stem
                metadata['author'] = 'Unknown'
        else:
            # PDF - use filename
            metadata['title'] = Path(input_path).stem
            metadata['author'] = 'Unknown'
        
        return metadata
    
    def process(self) -> str:
        """Main processing pipeline"""
        self.log_message(f"Starting normalization of: {self.input_path}")
        
        # Determine input type
        input_ext = Path(self.input_path).suffix.lower()
        
        # Extract chapters
        if input_ext == '.pdf':
            chapters = self.pdf_to_html_chapters(self.input_path)
            # Convert to 3-tuple format
            chapters = [(title, html, BeautifulSoup(html, 'lxml').get_text()) 
                       for title, html in chapters]
        elif input_ext == '.epub':
            chapters = self.extract_epub_chapters(self.input_path)
        else:
            raise ValueError(f"Unsupported file format: {input_ext}")
        
        # Deduplicate
        chapters = self.deduplicate_chapters(chapters)
        
        # Extract metadata
        metadata = self.extract_metadata(self.input_path)
        self.log_message(f"Metadata: {metadata['title']} by {metadata['author']}")
        
        # Build EPUB
        book = self.build_epub(chapters, metadata)
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, 'cleaned-book.epub')
        
        # Write EPUB
        epub.write_epub(output_path, book)
        self.log_message(f"Created EPUB: {output_path}")
        
        # Generate report
        self.generate_report(output_path)
        
        return output_path
    
    def generate_report(self, output_path: str):
        """Generate processing report"""
        report = f"""
{'='*60}
EPUB NORMALIZATION REPORT
{'='*60}
Input File: {self.input_path}
Output File: {output_path}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STATISTICS:
- Blank pages removed: {self.removed_blanks}
- Duplicate pages removed: {self.removed_duplicates}
- Total pages removed: {self.removed_blanks + self.removed_duplicates}

PROCESSING LOG:
"""
        for msg in self.log:
            report += f"  {msg}\n"
        
        report += f"\n{'='*60}\n"
        report += "VALIDATION: Run 'epubcheck cleaned-book.epub' to validate\n"
        report += f"{'='*60}\n"
        
        print(report)
        
        # Save report
        report_path = os.path.join(self.output_dir, 'normalization-report.txt')
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"\nReport saved to: {report_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python normalize_epub.py <input_file.epub|pdf> [output_dir]")
        print("\nExample:")
        print("  python normalize_epub.py mybook.epub")
        print("  python normalize_epub.py mybook.pdf output")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
    
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    normalizer = EPUBNormalizer(input_file, output_dir)
    
    try:
        output_path = normalizer.process()
        print(f"\n✓ Success! Clean EPUB created at: {output_path}")
        print(f"✓ Test with Kindle Previewer or run: epubcheck {output_path}")
    except Exception as e:
        print(f"\n✗ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
