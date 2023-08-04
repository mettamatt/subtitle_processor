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

DEBUG = False  # Set to True to enable debug logging

def get_intelligent_breakpoints(phrase, max_line_length=42):
    logging.debug(f'[START] get_intelligent_breakpoints')
    logging.debug(f'  Input phrase: "{phrase}" with max line length: {max_line_length}')

    doc = nlp(phrase)
    current_line_tokens = []  # To keep track of the current line as tokens
    lines = []
    last_token_idx = -1

    for idx, token in enumerate(doc):
        token_text = token.text
        logging.debug(f'  Iterating token {idx}: "{token_text}", dependency: {token.dep_}')

        last_token = doc[last_token_idx] if last_token_idx != -1 else None
        can_split = last_token.dep_ not in {"cc", "conj", "prep", "punct"} if last_token else False
        
        is_apostrophe_conj = last_token and last_token.text == "'" and last_token.dep_ == "conj"
        can_split = not is_apostrophe_conj and (last_token.dep_ not in {"cc", "conj", "prep", "punct"} if last_token else False)
    

        # Prepare a prospective line addition
        prospective_line_tokens = current_line_tokens + [token_text]
        prospective_line = ''.join(prospective_line_tokens).strip() + token.whitespace_

        # Handle contractions like "she's"
        if token_text.startswith("'") and last_token:
            current_line_tokens.extend([token_text, token.whitespace_])
            last_token_idx = idx
            logging.debug(f'  Token is a contraction, appended to current_line: {"".join(current_line_tokens).strip()}')
            continue

        if len(prospective_line) <= max_line_length or token.dep_ == "punct":
            current_line_tokens.extend([token_text, token.whitespace_])
            last_token_idx = idx
            logging.debug(f'  Token fits in line, appended to current_line: {prospective_line}')
        else:
            if current_line_tokens:
                lines.append(''.join(current_line_tokens).strip())
                logging.debug(f'  Line split, added to lines: "{"".join(current_line_tokens).strip()}"')
            current_line_tokens = [token_text, token.whitespace_]
            last_token_idx = idx

    if current_line_tokens:
        lines.append(''.join(current_line_tokens).strip())
        logging.debug(f'  Added remaining tokens to lines: "{"".join(current_line_tokens).strip()}"')

    # ensure that there are at most 2 lines
    while len(lines) > 2:
        lines[-2] += ' ' + lines[-1]
        logging.debug(f'  More than 2 lines, merged last two lines: "{lines[-2]}"')
        del lines[-1]

    logging.debug(f'  Output lines: {lines}')
    logging.debug(f'[END] get_intelligent_breakpoints\n')

    return [lines] if lines else []
    
def create_and_add_subtitle(lines, start_time, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start=None):
    logging.debug(f'[START] create_and_add_subtitle')
    
    # Flatten list of lists into single list of strings
    flattened_lines = [item for sublist in lines for item in sublist]
    
    # Join lines together, but ensure that there are at most 2 lines
    phrase = "\n".join(flattened_lines)
    split_phrase = phrase.split('\n')
    while len(split_phrase) > 2:
        split_phrase[-2] += ' ' + split_phrase[-1]
        del split_phrase[-1]
    phrase = "\n".join(split_phrase)
    
    # calculate duration based on phrase length
    duration_seconds = max(min(len(phrase) / MAX_READING_SPEED, MAX_DURATION), MIN_DURATION)
    duration_milliseconds = duration_seconds * 1000
    new_end = start_time + pysrt.SubRipTime(milliseconds=duration_milliseconds)

    # Check if the new_end time exceeds the start time of the next original subtitle.
    if next_sub_start is not None and new_end > next_sub_start:
        logging.debug(f'  Adjusting new_end because it exceeds next_sub_start')
        new_end = next_sub_start - pysrt.SubRipTime(milliseconds=1)
        
    new_sub = pysrt.SubRipItem(index=len(new_subs) + 1, text=phrase, start=start_time, end=new_end)
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

def integrity_check(original_text, adjusted_text):
    original_words = original_text.lower().split()
    adjusted_words = adjusted_text.lower().split()

    if original_words != adjusted_words:
        for i, (original_word, adjusted_word) in enumerate(zip(original_words, adjusted_words)):
            if original_word != adjusted_word:
                context_range = 5  # Number of words to include before and after the mismatch
                original_context = original_words[max(i - context_range, 0):min(i + context_range + 1, len(original_words))]
                adjusted_context = adjusted_words[max(i - context_range, 0):min(i + context_range + 1, len(adjusted_words))]
                logging.error(f"Integrity check failed at word {i}: Original word is '{original_word}', but adjusted word is '{adjusted_word}'.")
                logging.error(f"Original context: {' '.join(original_context)}")
                logging.error(f"Adjusted context: {' '.join(adjusted_context)}")
                return False
        if len(original_words) > len(adjusted_words):
            logging.error(f"Integrity check failed: Original text has additional words: {original_words[len(adjusted_words):]}")
            return False
        elif len(adjusted_words) > len(original_words):
            logging.error(f"Integrity check failed: Adjusted text has additional words: {adjusted_words[len(original_words):]}")
            return False
    else:
        logging.info("Integrity check passed: Original and adjusted texts match.")
        return True

def split_and_adjust_subtitles(input_file_path):
    logging.debug(f'[START] split_and_adjust_subtitles')
    orig_subs = pysrt.open(input_file_path)
    new_subs = []
    unique_new_subtitles = set()
    orig_to_new_subs = defaultdict(list)
    
    # Collect Original Text
    original_text = " ".join(sub.text for sub in orig_subs)

    for i, sub in enumerate(orig_subs):
        logging.debug(f'Processing subtitle {i}: "{sub.text}"')
        doc = nlp(sub.text)
        sentences = list(doc.sents)

        next_sub_start = orig_subs[i+1].start if i < len(orig_subs) - 1 else None

        original_start = sub.start

        for j, sentence in enumerate(sentences):
            phrase = sentence.text
            
            logging.debug(f'Processing sentence {j} in subtitle {i}: "{phrase}"')
            lines = get_intelligent_breakpoints(phrase, MAX_LINE_LENGTH)
            
            logging.debug(f'Split sentence "{phrase}" into lines: {lines}')
            if len(lines) > 0:
                logging.debug(f'Processing lines in sentence {j} in subtitle {i}: "{lines}"')
                original_start = create_and_add_subtitle(lines, original_start, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start)

    # Collect Adjusted Text
    adjusted_text = " ".join(new_sub.text for new_sub in new_subs)

    # Run the integrity check
    if not integrity_check(original_text, adjusted_text):
        logging.error("Integrity check failed: Original and adjusted texts do not match.")
    else:
        logging.info("Integrity check passed: Original and adjusted texts match.")

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
