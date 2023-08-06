# Subtitle Processor

Subtitle Processor is a Python script that processes an English subtitle file in the SubRip Text format (`.srt`). It adjusts the line breaks of the subtitles to make them easier to read. 


## Overview

This tool helps in refining the phrasing, splitting, and handling of hyphenated words and contractions. It is important to note that the script assumes the timings in the original subtitles are correct. The adjusted subtitles are then saved to a new file with an `.adjusted.srt` extension.

## Features

- Handles hyphenated words and contractions smartly.
- Adjusts subtitle lines based on predefined reading speed and maximum line length.
- Ensures each subtitle stays on the screen for a readable amount of time.
- Performs an integrity check to ensure word counts between original and adjusted texts match.

## Requirements

The script depends on a few Python libraries. Install the necessary requirements using:

```bash
pip install -r requirements.txt
```

### Content of `requirements.txt`

```
pysrt==1.1.2
spacy==3.6.0
```

## Usage

1. Navigate to the repository:

```bash
cd subtitle_processor
```

2. Run the script:

```bash
python subtitle_processor.py <path_to_subtitle_file>
```

Replace `<path_to_subtitle_file>` with the path to your `.srt` file.

Upon successful completion, you will see a message indicating the path to the adjusted subtitle file.

## Limitations

- The script currently supports only English subtitles.
- The tool assumes the timings in the original subtitle file are accurate and does not adjust them.
