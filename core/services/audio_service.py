import os
from gtts import gTTS
from django.conf import settings

def generate_report_audio(text_summary: str, output_filepath: str) -> str:
    """Convertit un texte en fichier audio MP3 en français."""
    tts = gTTS(text=text_summary, lang='fr', slow=False)
    tts.save(output_filepath)
    return output_filepath