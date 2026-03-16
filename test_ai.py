from ai_engine import generate_ai_reply

while True:
    user = input("You: ")
    if user.lower() in ["exit", "quit"]:
        break
    reply = generate_ai_reply(user, "unknown")
    print("AI:", reply)
