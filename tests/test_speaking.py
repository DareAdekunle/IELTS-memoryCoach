import sys
sys.path.append('.')
from app.services.speaking_service import get_prompt_set_by_id
from app.services.speaking_evaluator_service import evaluate_speaking_attempt

# Load the first prompt set
prompt_set = get_prompt_set_by_id('speaking_001')

# Dummy transcriptions to test the service
part1_responses = {
    '0': 'I prefer spending time with family because they understand me better and we have a lot of shared memories together.',
    '1': 'I keep in touch with my friends quite regularly. We usually message each other every day and meet up maybe once a week.',
    '2': 'Yes my friendships have definitely changed. As I have gotten older I have fewer friends but the friendships I have are much deeper and more meaningful.',
    '3': 'I think loyalty and honesty are the most important qualities in a good friend. Without these two things you cannot really trust someone.'
}

part2_response = (
    "I would like to talk about my uncle who has had a very positive influence on my life. "
    "He is my mother's brother and I have known him my whole life. "
    "What he did that influenced me the most was when he encouraged me to pursue education "
    "even when my family was going through difficult financial times. "
    "He told me that education was the one thing nobody could ever take away from you. "
    "His influence has been important because it gave me the motivation to keep studying "
    "when things were hard."
)

part3_responses = {
    '0': 'I think some people have more influence because they have a combination of charisma and expertise. People tend to follow those who both know what they are talking about and can communicate it in a compelling way.',
    '1': 'I think celebrities can be good role models but it depends very much on the individual. Some use their platform responsibly but others do not behave in ways young people should copy.',
    '2': 'The internet has completely changed how people are influenced. Before the internet people were mainly influenced by those around them but now someone on the other side of the world can influence millions through social media.'
}

print('Evaluating speaking attempt...')
print('This will call Qwen and TTS so may take 20-30 seconds...')
print()

result = evaluate_speaking_attempt(
    prompt_set=prompt_set,
    part1_responses=part1_responses,
    part2_response=part2_response,
    part3_responses=part3_responses,
    memories=[]
)

if result['success']:
    print('✅ Evaluation successful!')
    print()
    print('=== Examiner Feedback ===')
    print(result['feedback_text'])
    print()
    print('=== Scores ===')
    scores = result['scores']
    if scores:
        print(f"  Fluency and Coherence: {scores.get('fluency_coherence', '?')} / 9")
        print(f"  Lexical Resource: {scores.get('lexical_resource', '?')} / 9")
        print(f"  Grammatical Range: {scores.get('grammatical_range', '?')} / 9")
        print(f"  Pronunciation Clarity: {scores.get('pronunciation_clarity', '?')} / 9")
        print(f"  Overall Band: {scores.get('overall_band', '?')}")
    print()
    if result['tts_success']:
        print('✅ TTS audio generated successfully')
        with open('test_examiner_feedback.wav', 'wb') as f:
            f.write(result['audio_bytes'])
        print('   Saved to test_examiner_feedback.wav — open to hear Cherry!')
    else:
        print('⚠️  TTS generation had an issue')
else:
    print(f'❌ Evaluation failed: {result["error"]}')