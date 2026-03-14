def keyword_classifier(text):
    text = text.lower()
    
    # Simple keyword mapping logic
    if "wine" in text or "vineyard" in text or "sula" in text:
        return {"segment": "Wine Enthusiast", "score": 60, "urgency": "medium"}
    
    if "resort" in text or "stay" in text or "looking for" in text:
        if "weekend" in text:
            return {"segment": "Family Weekend", "score": 70, "urgency": "high"}
        return {"segment": "Luxury Couple", "score": 55, "urgency": "low"}
        
    if "temple" in text or "shirdi" in text or "trimbakeshwar" in text:
        return {"segment": "Spiritual Seeker", "score": 80, "urgency": "high"}
        
    if "work" in text or "remotely" in text or "wifi" in text:
        return {"segment": "Digital Nomad", "score": 65, "urgency": "medium"}
        
    if "group" in text or "corporate" in text or "team" in text:
        return {"segment": "Corporate Group", "score": 50, "urgency": "medium"}

    return {"segment": "Irrelevant", "score": 10, "urgency": "low"}
 village_keywords = ["nashik", "travel", "visit", "trip"]
 if any(kw in text for kw in village_keywords):
     return {"segment": "Backpacker", "score": 30, "urgency": "low"}
     
 return {"segment": "Irrelevant", "score": 0, "urgency": "low"}
