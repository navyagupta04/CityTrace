from anpr.vision import vote
from anpr.plates import normalize

def aggregate(reads,threshold=.8):
    text,confidence=vote(reads);normal=normalize(text)
    valid=bool(getattr(normal,'valid',getattr(normal,'format_valid',False)))
    accepted=bool(text and valid and confidence>=threshold)
    return {'text':text if accepted else None,'format_valid':valid,'vote_confidence':confidence,'n_reads':len(reads),'status':'read' if accepted else 'abstain','alternatives':[{'text':text,'score':confidence}] if text else []}
