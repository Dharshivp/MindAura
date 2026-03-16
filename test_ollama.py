from ollama import Client

# 1️⃣ Create the client
client = Client()

# 2️⃣ List all available models
models = client.list()  # returns special Models object

# 3️⃣ Print available models safely
print("Available models:")
first_model_name = None  # will store the first model name

for category, model_list in models:  # unpack tuple (category, [Model objects])
    print("Category:", category)
    for m in model_list:
        print("-", m.model)
        if first_model_name is None:  # save the first model
            first_model_name = m.model

# 4️⃣ Use the first available model
if first_model_name is None:
    print("No models found!")
    exit()

print("\nUsing model:", first_model_name)

# 5️⃣ Generate text
response = client.generate(model=first_model_name, prompt="Hello, how are you today?")

# 6️⃣ Print only the AI's text
print("\nAI Response:")
print(response.response)
