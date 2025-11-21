# EPUB/PDF Normalizer for Kindle

A production-ready tool to normalize EPUB and PDF files into clean, Kindle-compatible eBooks that pass KDP validation.

## Features

- ✅ Reads EPUB and PDF files
- ✅ Removes duplicate pages (hash-based + fuzzy matching at 95% threshold)
- ✅ Removes blank pages (< 10 characters)
- ✅ Normalizes formatting (fonts, spacing, margins)
- ✅ Preserves book structure (titles, chapters, heading hierarchy)
- ✅ Generates valid content.opf and toc.ncx
- ✅ Minimal Kindle-optimized CSS
- ✅ Adds/fixes metadata (title, author, language, UUID, publisher, date)
- ✅ Reflowable layout (not fixed)
- ✅ Generates processing report

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make script executable (optional)
chmod +x normalize_epub.py
```

## Usage

### Basic Usage

```bash
# Normalize an EPUB file
python normalize_epub.py input.epub

# Normalize a PDF file
python normalize_epub.py input.pdf

# Specify custom output directory
python normalize_epub.py input.epub my_output_folder
```

### Output

The script creates:
- `output/cleaned-book.epub` - The normalized EPUB file
- `output/normalization-report.txt` - Processing report with statistics

## How It Works

### 1. Input Processing
- **PDF**: Converts to structured HTML using PyMuPDF, detecting headings by font size
- **EPUB**: Extracts existing chapters and content

### 2. Deduplication
- **Hash-based**: SHA256 of normalized text
- **Similarity-based**: Fuzzy matching with 95% threshold using RapidFuzz
- Logs ambiguous cases for manual review

### 3. Blank Page Detection
- Pages with < 10 characters
- Pages with only whitespace
- Image-only pages with no text

### 4. Normalization
- Removes inline styles and font tags
- Standardizes paragraph spacing and indentation
- Normalizes line breaks
- Applies minimal CSS for reflowable reading

### 5. EPUB Generation
- Valid content.opf with complete metadata
- Working table of contents (TOC)
- NCX file for older e-readers
- Proper chapter navigation

### 6. Metadata
- Title (extracted or from filename)
- Author (extracted or "Unknown")
- Language (default: "en")
- UUID identifier
- Publisher (default: "Self-published")
- Publication date

## CSS Styling

The tool applies minimal, Kindle-friendly CSS:
- Serif font family
- 1.5 line height
- 1.5em paragraph indentation
- Justified text alignment
- Proper heading hierarchy (h1-h6)
- Support for bold and italic

## Validation

After processing, validate your EPUB:

```bash
# Install EPUBCheck (Java required)
# Download from: https://github.com/w3c/epubcheck/releases

# Validate
java -jar epubcheck.jar output/cleaned-book.epub

# Or use online validator
# https://validator.idpf.org/
```

## Testing with Kindle

1. **Kindle Previewer**: Download from Amazon and open the generated EPUB
2. **Send to Kindle**: Email the EPUB to your Kindle email address
3. **KDP Upload**: Upload directly to Kindle Direct Publishing

## Example Output

```
[LOG] Starting normalization of: mybook.epub
[LOG] Reading EPUB: mybook.epub
[LOG] Extracted 45 chapters from EPUB
[LOG] Removed duplicate (hash): Chapter 3
[LOG] Removed duplicate (similarity): Chapter 15
[LOG] Kept 43 unique chapters
[LOG] Metadata: My Book Title by John Doe
[LOG] Created EPUB: output/cleaned-book.epub

============================================================
EPUB NORMALIZATION REPORT
============================================================
Input File: mybook.epub
Output File: output/cleaned-book.epub

STATISTICS:
- Blank pages removed: 3
- Duplicate pages removed: 2
- Total pages removed: 5

✓ Success! Clean EPUB created at: output/cleaned-book.epub
```

## Dependencies

- **ebooklib**: EPUB reading/writing
- **beautifulsoup4**: HTML parsing and manipulation
- **lxml**: XML processing
- **PyMuPDF**: PDF text extraction
- **Pillow**: Image processing
- **rapidfuzz**: Fuzzy text matching for deduplication

## Troubleshooting

### "Permission denied" error
Ensure you have write permissions in the output directory.

### PDF conversion issues
Some PDFs with complex layouts may not convert perfectly. The tool uses text extraction which works best with text-based PDFs (not scanned images).

### Missing metadata
If metadata cannot be extracted, the tool uses filename as title and "Unknown" as author. You can manually edit the EPUB metadata after generation.

### EPUBCheck errors
The tool generates valid EPUBs, but if you encounter errors:
1. Check the normalization report for warnings
2. Ensure input file is not corrupted
3. Try re-running with a different input

## Advanced Usage

### Modify similarity threshold
Edit `normalize_epub.py` line with `threshold=95.0` to adjust duplicate detection sensitivity (0-100).

### Customize CSS
Edit the `create_minimal_css()` method to adjust styling while keeping it Kindle-compatible.

### Add custom metadata
Modify the `extract_metadata()` method to include additional metadata fields.

## License

This tool is provided as-is for personal and commercial use.

## Support

For issues or questions, refer to the processing report and logs generated during normalization.
