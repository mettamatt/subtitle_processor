# Standard library imports
import logging
import os
import sys
from collections import defaultdict

# Third party imports
import pysrt
import spacy

try:
    nlp = spacy.load('en_core_web_sm')
except OSError:
    spacy_download('en_core_web_sm')
    nlp = spacy.load('en_core_web_sm')

logging.basicConfig(
    level=logging.DEBUG, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

MAX_READING_SPEED = 20
MAX_LINE_LENGTH = 42
MIN_DURATION = 1
MAX_DURATION = 6

DEBUG = True  # Set to True to enable debug logging

def get_intelligent_breakpoints(phrase, max_line_length=42):
    logging.debug(f'[START] get_intelligent_breakpoints')
    logging.debug(f'  Input phrase: "{phrase}"')

    doc = nlp(phrase)
    lines = []
    current_line = ''
    second_line = ''

    for token in doc:
        token_text = token.text_with_ws  # use text_with_ws instead of text + whitespace_
        logging.debug(f'  Current token: "{token_text}", dep_: {token.dep_}')

        last_token = nlp(current_line.rstrip())[-1] if current_line else None
        can_split = last_token.dep_ not in {"cc", "conj", "prep", "punct"} if last_token else False

        # Prepare a prospective line addition
        prospective_line = current_line + second_line + token_text.strip() if not token_text.isalnum() else current_line + second_line + token_text

        if len(prospective_line.rstrip()) <= max_line_length:
            current_line += second_line
            second_line = ''
            if not token_text.isalnum():
                current_line += token_text.strip()
            else:
                current_line += token_text
            logging.debug(f'  Appended token to current_line: "{current_line}"')

        elif can_split:
            # If the prospective line is too long but can be split, add second_line to current_line
            # And add token_text to second_line
            current_line += second_line
            second_line = token_text.strip() if not token_text.isalnum() else token_text
            logging.debug(f'  Appended token to second_line: "{second_line}"')

        else:
            logging.debug(f'  Length of prospective line exceeds max_line_length')
            if current_line.strip():
                line_to_add = current_line.replace('\n', ' ').strip()
                lines.append(line_to_add)
                logging.debug(f'  Added to lines: "{line_to_add}"')
                current_line = second_line
                second_line = token_text.strip() if not token_text.isalnum() else token_text

    if current_line.strip():
        line_to_add = current_line.replace('\n', ' ').strip()
        lines.append(line_to_add)
        logging.debug(f'  Added to lines: "{line_to_add}"')

    if second_line.strip():
        line_to_add = second_line.replace('\n', ' ').strip()
        lines.append(line_to_add)
        logging.debug(f'  Added to lines: "{line_to_add}"')

    logging.debug(f'  Output lines: {lines}')
    logging.debug(f'[END] get_intelligent_breakpoints\n')

    return lines
    
def create_and_add_subtitle(phrase, start_time, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start=None):
    logging.debug(f'[START] create_and_add_subtitle')
    # calculate duration based on phrase length
    duration_seconds = max(min(len(phrase) / MAX_READING_SPEED, MAX_DURATION), MIN_DURATION)
    duration_milliseconds = duration_seconds * 1000
    new_end = start_time + pysrt.SubRipTime(milliseconds=duration_milliseconds)

    # Check if the new_end time exceeds the start time of the next original subtitle.
    if next_sub_start is not None and new_end > next_sub_start:
        logging.debug(f'  Adjusting new_end because it exceeds next_sub_start')
        new_end = next_sub_start - pysrt.SubRipTime(milliseconds=1)
        
    new_sub = pysrt.SubRipItem(index=len(new_subs) + 1, text=phrase.strip(), start=start_time, end=new_end)
    new_sub_tuple = (new_sub.text, str(new_sub.start), str(new_sub.end))

    if new_sub_tuple not in unique_new_subtitles:
        new_subs.append(new_sub)
        unique_new_subtitles.add(new_sub_tuple)
        logging.debug(f'  Added new subtitle to list: "{new_sub.text}"')
    else:
        logging.debug(f'  Skipped adding subtitle as it already exists: "{new_sub.text}"')

    orig_to_new_subs[i].append(new_sub.text)

    logging.debug(f'  Created new subtitle: "{new_sub.text}"')
    logging.debug(f'  New subtitle start time: {new_sub.start}')
    logging.debug(f'  New subtitle end time: {new_sub.end}')

    logging.debug(f'[END] create_and_add_subtitle')
    # return the new end time
    return new_end + pysrt.SubRipTime(milliseconds=1)

def split_and_adjust_subtitles(input_file_path):
    logging.debug(f'[START] split_and_adjust_subtitles')
    orig_subs = pysrt.open(input_file_path)
    new_subs = []
    unique_new_subtitles = set()
    orig_to_new_subs = defaultdict(list)

    for i, sub in enumerate(orig_subs):
        logging.debug(f'Processing subtitle {i}: "{sub.text}"')
        doc = nlp(sub.text)
        sentences = list(doc.sents)

        next_sub_start = orig_subs[i+1].start if i < len(orig_subs) - 1 else None

        original_start = sub.start

        for j, sentence in enumerate(sentences):
            phrase = sentence.text.strip()
            
            logging.debug(f'Processing sentence {j} in subtitle {i}: "{phrase}"')
            lines = get_intelligent_breakpoints(phrase, MAX_LINE_LENGTH)
            
            logging.debug(f'Split sentence "{phrase}" into lines: {lines}')
            for k, line in enumerate(lines):
                if len(line) > 0:
                    logging.debug(f'Processing line {k} in sentence {j} in subtitle {i}: "{line}"')
                    original_start = create_and_add_subtitle(line, original_start, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start)

    subs = pysrt.SubRipFile(items=new_subs)
    output_file_path = os.path.splitext(input_file_path)[0] + '.adjusted.srt'
    subs.save(output_file_path, encoding='utf-8')

    logging.debug(f'[END] split_and_adjust_subtitles')
    return output_file_path, orig_to_new_subs
    
if __name__ == "__main__":
    # Check if command line argument is provided
    if len(sys.argv) < 2:
        print("Usage: python subtitle_processor.py /path/to/subtitle/file.srt")
        sys.exit(1)

    # Get the path to the .srt file from the command line arguments
    input_file_path = sys.argv[1]

    # Call the function to adjust the subtitles
    split_and_adjust_subtitles(input_file_path)
