import ollama

def generate_ai_reply(text, emotion):
    try:
        # This calls the llama3 model on your local machine
        response = ollama.chat(
            model="llama3:latest",
            messages=[
                {"role": "system", "content": "You are a helpful student assistant."},
                {"role": "user", "content": f"The student feels {emotion}. Message: {text}"}
            ]
        )
        return response['message']['content']
    except Exception as e:
        print(f"OLLAMA ERROR: {e}")
        return "⚠️ I can't reach my local brain. Please check the Ollama terminal!"