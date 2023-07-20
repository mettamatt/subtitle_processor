# Standard library imports
import logging
import os
import re
import sys
from collections import defaultdict, Counter

# Third party imports
import pysrt
from nltk import word_tokenize, pos_tag, sent_tokenize
from nltk.util import ngrams

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

def join_words(words):
    output = ''
    for word in words:
        if word in {',', '.', '!', '?', ':', ';'}:
            output = output.rstrip() + word + ' '
        else:
            output += word + ' '
    return output.rstrip()
    
def ngram_counter(words, n=2):
    return Counter(ngrams(words, n))

def text_normalization_for_integrity_check(text):
    text = text.strip().lower()
    return re.sub(r'\s+', ' ', text)

def intelligent_breakpoint(phrase, max_line_length):
    tagged = pos_tag(word_tokenize(phrase))

    if DEBUG:
        debug_info = f'[DEBUG START] intelligent_breakpoint\n  [DEBUG] Tagged words: {tagged}\n'
    
    if len(phrase) <= max_line_length or ' ' not in phrase:
        breakpoint = len(phrase) - 1

        if DEBUG:
            debug_info += f'  [DEBUG] Early return breakpoint: {breakpoint}\n[DEBUG END] intelligent_breakpoint\n'
            logging.debug(debug_info)

        return phrase, ""

    min_subtitle_length = max_line_length // 4
    breakpoint = next((i for i, (word, tag) in enumerate(tagged[:max_line_length]) if tag == 'CC'), -1)
    
    while len(' '.join(word for word, tag in tagged[:breakpoint+1]).strip()) < min_subtitle_length:
        try:
            breakpoint = next(i for i, (word, tag) in enumerate(tagged[breakpoint+1:max_line_length], start=breakpoint+1) if tag == 'CC')
        except StopIteration:
            break

    if breakpoint != -1 and (breakpoint + 1) < len(tagged) and tagged[breakpoint+1][1] in {'PRP', 'PRP$', 'WP', 'WP$'}:
        breakpoint -= 1

    if breakpoint != -1 and (breakpoint + 1) < len(tagged) and tagged[breakpoint+1][1] in {'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ'} or tagged[breakpoint][1] in {'RB', 'RBR', 'RBS'}:
        breakpoint -= 1

    if breakpoint == -1:
        breakpoint = phrase.rfind(' ', 0, max_line_length)

    if breakpoint == -1 or breakpoint >= max_line_length:
        breakpoint = max_line_length - 1

    first_phrase = join_words(word for word, tag in tagged[:breakpoint+1])
    remaining_phrase = join_words(word for word, tag in tagged[breakpoint+1:])

    # If the remaining phrase starts with a comma, move the comma to the end of the first phrase
    if remaining_phrase.startswith(", "):
        first_phrase += ","
        remaining_phrase = remaining_phrase[2:]

    if DEBUG:
        debug_info += f'  [DEBUG] Final phrase split: "{first_phrase}" and "{remaining_phrase}"\n[DEBUG END] intelligent_breakpoint\n'
        logging.debug(debug_info)

    return first_phrase, remaining_phrase
    
def create_and_add_subtitle(phrase, start_time, new_subs, new_subs_set, orig_to_new_subs, sub, i, next_sub_start=None):
    # calculate duration based on phrase length
    duration_seconds = max(min(len(phrase) / MAX_READING_SPEED, MAX_DURATION), MIN_DURATION)
    duration_milliseconds = duration_seconds * 1000
    new_end = start_time + pysrt.SubRipTime(milliseconds=duration_milliseconds)

    # Check if the new_end time exceeds the start time of the next original subtitle.
    if next_sub_start is not None and new_end > next_sub_start:
        new_end = next_sub_start - pysrt.SubRipTime(milliseconds=1)
        
    new_sub = pysrt.SubRipItem(index=len(new_subs) + 1, text=phrase.strip(), start=start_time, end=new_end)
    new_sub_tuple = (new_sub.text, str(new_sub.start), str(new_sub.end))

    if new_sub_tuple not in new_subs_set:
        new_subs.append(new_sub)
        new_subs_set.add(new_sub_tuple)

    orig_to_new_subs[i].append(new_sub.text)

    if DEBUG:
        logging.debug(f'Linked new subtitle: {new_sub.text} to original: {sub.text}')

    # return the new end time
    return new_end + pysrt.SubRipTime(milliseconds=1)

def adjust_subtitles(input_file_path):
    orig_subs = pysrt.open(input_file_path)
    new_subs = []
    new_subs_set = set()
    orig_to_new_subs = defaultdict(list)

    for i, sub in enumerate(orig_subs):
        sentences = sent_tokenize(sub.text)
        phrases = [phrase for sentence in sentences for phrase in re.split(r'(?<=,),', sentence)]
    
        next_sub_start = orig_subs[i+1].start if i < len(orig_subs) - 1 else None

        original_start = sub.start

        for phrase in phrases:
            phrase = phrase.strip()

            while len(phrase) > MAX_LINE_LENGTH:
                first_phrase, remaining_phrase = intelligent_breakpoint(phrase, MAX_LINE_LENGTH)
                original_start = create_and_add_subtitle(first_phrase, original_start, new_subs, new_subs_set, orig_to_new_subs, sub, i, next_sub_start)
                phrase = remaining_phrase.strip()

            if len(phrase) > 0:
                original_start = create_and_add_subtitle(phrase, original_start, new_subs, new_subs_set, orig_to_new_subs, sub, i, next_sub_start)

    subs = pysrt.SubRipFile(items=new_subs)
    output_file_path = os.path.splitext(input_file_path)[0] + '.adjusted.srt'
    subs.save(output_file_path, encoding='utf-8')

    original_bigrams = ngram_counter(word for sub in orig_subs for word in word_tokenize(text_normalization_for_integrity_check(sub.text)))
    new_bigrams = ngram_counter(word for sub in new_subs for word in word_tokenize(text_normalization_for_integrity_check(sub.text)))

    missing_bigrams = original_bigrams - new_bigrams
    extra_bigrams = new_bigrams - original_bigrams

    if len(missing_bigrams) != 0:
        print(f'Error: Missing bigrams: {missing_bigrams}')

    if len(extra_bigrams) != 0:
        print(f'Error: Extra bigrams: {extra_bigrams}')

    return output_file_path, orig_to_new_subs
    
if __name__ == "__main__":
    # Check if command line argument is provided
    if len(sys.argv) < 2:
        print("Usage: python subtitle_processor.py /path/to/subtitle/file.srt")
        sys.exit(1)

    # Get the path to the .srt file from the command line arguments
    input_file_path = sys.argv[1]

    # Call the function to adjust the subtitles
    adjust_subtitles(input_file_path)
