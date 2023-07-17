# Subtitle Processor

Subtitle Processor is a Python script that processes `.srt` subtitle files. It adjusts the timings and text length of each subtitle based on predefined constants. It also applies an initial offset (lead-in offset) to all the subtitles. The script loosely follows the guidelines of the [Netflix Timed Text Style Guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements).

## Requirements

This script requires Python and the following Python packages:

- `argparse`
- `datetime`
- `pysrt`
- `re`
- `sys`

You can install the required Python packages with pip:

```bash
pip install argparse pysrt
```

## Usage

To use this script, you need to provide the path to the `.srt` file to be processed as an argument. You can also optionally provide a lead-in offset (in seconds) that will be applied to the first subtitle in the `.srt` file. If you want to process multiple files, you can provide the paths of multiple `.srt` files.

Here is an example:

```bash
python subtitle_processor.py /path/to/file1.srt /path/to/file2.srt --lead-in-offset 1.5
```

If the lead-in offset is not provided, the default value of 0.0 seconds is used.

## Output

The script will create new `.srt` files with adjusted subtitles for each input file. The new files will be saved in the same directory as the corresponding input files, preserving the original files. 

For example:

```bash
python subtitle_processor.py /path/to/file.srt --lead-in-offset 1.5
```

Will output:

```
/path/to/file.adjusted.srt
```

This signifies that the processing has been completed and the adjusted `.srt` file is available at `/path/to/file.adjusted.srt`.

Remember that the script does not delete or modify the original `.srt` files, it merely reads them and creates new, adjusted versions. This way, your original subtitle data remains intact and unmodified.

## Constants

The script uses the following constants for adjusting subtitle timings and text length:

- `MIN_DURATION`: The minimum duration of a subtitle (833 milliseconds)
- `MIN_DURATION_SECONDS`: The minimum duration in seconds (5/6 seconds)
- `MAX_DURATION`: The maximum duration of a subtitle (7 seconds)
- `MAX_TEXT_LEN`: The maximum length of text in a subtitle (42 characters)
- `TRANSITION_GAP`: The transition gap between two subtitles (120 milliseconds)

These constants can be adjusted to fit your needs.

## Functions

The script includes the following main functions:

- `adjust_times(subtitle, next_subtitle)`: Adjusts the end time of a subtitle based on its duration and the start time of the next subtitle.
- `adjust_text(subtitle, max_len=MAX_TEXT_LEN)`: Adjusts the text of a subtitle by replacing ellipses and potentially splitting the text into multiple lines.
- `process_srt_file(file_name, offset)`: Processes an `.srt` file by applying an offset and adjusting the timings and text length of each subtitle.

And these helper functions:

- `replace_ellipses(text)`: Replaces all occurrences of '...' in the text with the unicode character for ellipsis '\u2026'.
- `subriptime_total_seconds(subriptime)`: Converts a SubRipTime object to its equivalent in total seconds.
- `apply_lead_in_offset(subtitles, offset)`: Applies an initial offset to the start time of the first subtitle.

## Errors

In case of an error (like the provided `.srt` file not being found or not being a valid `.srt` file), the script will print the error message and exit with status code 1.