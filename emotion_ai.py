from transformers import pipeline
import os

# Load the model from your local folder
# We use 'cpu' because most laptops don't have the GPU power of Colab
model_path = os.path.join(os.getcwd(), "saved_model")
# Change your line to this:
classifier = pipeline("text-classification", model=model_path, tokenizer=model_path, device=-1)

def analyze_emotion(text):
    # Get prediction from your trained BERT model
    result = classifier(text)[0]
    label_id = result['label'] # This will be 'LABEL_0', 'LABEL_1', etc.
    score = result['score']

    # Map the labels to your app's logic
    # 0: Normal, 1: Depression, 2: Suicidal, 3: Anxiety
    label_map = {
        "LABEL_0": ("Normal", 1),
        "LABEL_1": ("Depression", 4),
        "LABEL_2": ("Suicidal", 5),
        "LABEL_3": ("Anxiety", 3)
    }

    emotion, stress_level = label_map.get(label_id, ("Neutral", 2))
    
    return emotion, stress_level