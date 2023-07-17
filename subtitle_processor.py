import argparse
import datetime
import pysrt
import re
import sys

# Constants
MIN_DURATION = pysrt.srttime.SubRipTime(0, 0, 0, 833)
MIN_DURATION_SECONDS = 5/6
MAX_DURATION = pysrt.srttime.SubRipTime(0, 0, 7, 0)
MAX_TEXT_LEN = 42
TRANSITION_GAP = pysrt.srttime.SubRipTime(0, 0, 0, 120)

# Convert SubRipTime to seconds
MIN_DURATION_SECONDS = (MIN_DURATION.hours * 3600) + (MIN_DURATION.minutes * 60) + MIN_DURATION.seconds + (MIN_DURATION.milliseconds / 1000.0)
MAX_DURATION_SECONDS = (MAX_DURATION.hours * 3600) + (MAX_DURATION.minutes * 60) + MAX_DURATION.seconds + (MAX_DURATION.milliseconds / 1000.0)

# Regular Expression
PUNCTUATION_PATTERN = re.compile(r'[.!?]')

# Helper Functions
def replace_ellipses(text):
    return text.replace("...", "\u2026")

def subriptime_total_seconds(subriptime):
    total_seconds = (subriptime.hours * 3600) + (subriptime.minutes * 60) + subriptime.seconds + (subriptime.milliseconds / 1000.0)
    return total_seconds

def apply_lead_in_offset(subtitles, offset):
    if len(subtitles) > 0:
        subtitles[0].start.shift(seconds=offset)
    return subtitles

# Main Functions
def adjust_times(subtitle, next_subtitle):
    start_time = subtitle.start
    end_time = subtitle.end
    next_start_time = next_subtitle.start

    duration = subriptime_total_seconds(end_time - start_time)
    
    if duration < MIN_DURATION_SECONDS:
        end_time = min(start_time + MIN_DURATION, next_start_time - TRANSITION_GAP)
    elif duration > MAX_DURATION_SECONDS:
        end_time = start_time + MAX_DURATION
    
    if end_time >= next_start_time:  
        end_time = next_start_time - TRANSITION_GAP

    subtitle.end = end_time
    return subtitle

def adjust_text(subtitle, max_len=MAX_TEXT_LEN):
    subtitle.text = replace_ellipses(subtitle.text)
    
    if len(subtitle.text) <= max_len:
        return subtitle

    sentences = re.split(r'(?<=[.,:;!?])\s+', subtitle.text)
    split_idx = -1

    for i, sentence in enumerate(sentences):
        if len(''.join(sentences[:i+1])) > max_len:
            split_idx = i
            break

    if split_idx != -1:
        subtitle.text = ' '.join(sentences[:split_idx]) + '\n' + ' '.join(sentences[split_idx:])
    else:
        subtitle.text = subtitle.text[:max_len] + '\n' + subtitle.text[max_len:]

    lines = subtitle.text.split('\n')
    while len(lines) > 2 or (len(lines) == 2 and len(lines[0].split()) <= 2):
        if len(lines) == 2:
            lines[0] = lines[0] + ' ' + lines[1].split(' ', 1)[0]
            lines[1] = ' '.join(lines[1].split(' ', 1)[1:])
        else:
            split_idx = lines[0].rfind(' ')
            if split_idx == -1: 
                break
            lines[0] = lines[0][:split_idx]
            lines[1] = lines[0][split_idx+1:] + ' ' + lines[1]
    
    subtitle.text = '\n'.join(lines)
    return subtitle

def process_srt_file(file_name, offset):
    try:
        subtitles = pysrt.open(file_name)
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File {file_name} not found.")
    except pysrt.Error:
        raise ValueError(f"Error: Could not read file {file_name}. Please check if it is a valid .srt file.")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {str(e)}")

    subtitles = apply_lead_in_offset(subtitles, lead_in_offset)

    adjusted_subtitles = []
    
    for i in range(len(subtitles) - 1):
        subtitle = subtitles[i]
        next_subtitle = subtitles[i+1]

        if subtitle.end > next_subtitle.start:
            subtitle.end = next_subtitle.start

        original_start = subtitle.start
        original_end = subtitle.end
        original_text = subtitle.text

        subtitle = adjust_times(subtitle, next_subtitle)
        subtitle = adjust_text(subtitle)

        if original_start != subtitle.start or original_end != subtitle.end or original_text != subtitle.text:
            print(f"Subtitle {subtitle.index} has been adjusted:")
            print(f"Original: Start: {original_start}, End: {original_end}, Text: {original_text}")
            print(f"Adjusted: {subtitle}")

        adjusted_subtitles.append(subtitle)

    adjusted_subtitles.append(adjust_times(subtitles[-1], subtitles[-1]))

    new_file_name = file_name.rsplit('.', 1)[0] + '.adjusted.srt'
    pysrt.SubRipFile(adjusted_subtitles).save(new_file_name, encoding='utf-8')
    return new_file_name

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script processes .srt subtitle files. It adjusts the timings and text length of each subtitle based on predefined constants. It also applies an initial offset to all subtitles.")
    parser.add_argument('file', type=str, help='The path to the .srt file to be processed.')
    parser.add_argument('-l', '--lead-in-offset', type=float, default=0.0, help='The initial offset (in seconds) to be applied to the first subtitle in the .srt file. If not provided, the default is 0.0.')

    args = parser.parse_args()

    try:
        file_path = args.file
        lead_in_offset = args.lead_in_offset
        if lead_in_offset < 0:
            raise ValueError("Error: Lead-in offset cannot be negative.")
        result = process_srt_file(file_path, lead_in_offset)
        print(result)
    except Exception as e:
        print(e)
        sys.exit(1)