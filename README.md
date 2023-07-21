# Subtitle Processor

Subtitle Processor is a Python script that processes subtitle files in the SubRip Text format (`.srt`). It adjusts the timing and line breaks of the subtitles to make them easier to read. 

## Overview

The script works by loading a language model from the `spacy` library to analyze the text of the subtitles. It then processes each subtitle, splits sentences into lines, and adjusts the timing of each subtitle. The new subtitles are saved to a new `.srt` file with the same name as the original file, but with `.adjusted` added before the file extension.

## Constants

The script defines the following constants:

- `MAX_READING_SPEED`: The maximum reading speed in characters per second. Used to calculate the duration of each subtitle.
- `MAX_LINE_LENGTH`: The maximum length of a line of subtitle text.
- `MIN_DURATION`: The minimum duration of a subtitle in seconds.
- `MAX_DURATION`: The maximum duration of a subtitle in seconds.
- `DEBUG`: A boolean variable that enables or disables debug logging. When set to `True`, the script logs additional information about its operation.

## Functions

The script uses the following functions:

- `get_intelligent_breakpoints(phrase, max_line_length)`: Takes a phrase and breaks it into lines, considering the maximum line length and the structure of the language.
- `create_and_add_subtitle(phrase, start_time, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start)`: Creates a new subtitle with adjusted timing and adds it to the list of new subtitles, avoiding duplicate subtitles.
- `split_and_adjust_subtitles(input_file_path)`: The main function that opens the original subtitle file, processes each subtitle, splits sentences into lines, and adjusts the timing of each subtitle.

## Requirements

The script requires the following Python libraries:

- `pysrt==1.1.2`: A Python library for editing .srt files.
- `spacy==3.6.0`: A library for advanced Natural Language Processing in Python.

These dependencies can be installed by running the command `pip install -r requirements.txt` in your terminal, in the same directory as the `requirements.txt` file.

## Usage

To use the script, run it as follows:

```bash
python subtitle_processor.py /path/to/subtitle/file.srt
```

Replace `/path/to/subtitle/file.srt` with the path to the `.srt` file that you want to process.

## License

This project is licensed under the terms of the MIT license. See the `LICENSE` file for details.