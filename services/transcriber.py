import assemblyai as aai
import os
from config import ASSEMBLYAI_API_KEY
import asyncio
from concurrent.futures import ThreadPoolExecutor

aai.settings.api_key = ASSEMBLYAI_API_KEY

executor = ThreadPoolExecutor(max_workers=5)

def sync_transcribe(file_path: str, language_code: str = "auto", diarization: bool = False) -> aai.Transcript:
    transcriber = aai.Transcriber()
    
    if language_code == "auto":
        config = aai.TranscriptionConfig(
            speaker_labels=diarization,
            language_detection=True
        )
    else:
        config = aai.TranscriptionConfig(
            speaker_labels=diarization,
            language_code=language_code
        )
    
    transcript = transcriber.transcribe(file_path, config)
    return transcript

async def async_transcribe(file_path: str, language_code: str = "auto", diarization: bool = False) -> aai.Transcript:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_transcribe, file_path, language_code, diarization)

def format_transcript(transcript: aai.Transcript) -> str:
    if transcript.error:
        return f"Ошибка транскрибации: {transcript.error}"
    
    if not transcript.utterances:
        return transcript.text

    # Форматирование с учетом спикеров
    formatted_text = ""
    for utterance in transcript.utterances:
        speaker = f"Спикер {utterance.speaker}"
        formatted_text += f"**{speaker}**: {utterance.text}\n\n"
        
    return formatted_text.strip()
