import random
def split_videos(ids,seed=26127):
    ids=sorted(set(ids));random.Random(seed).shuffle(ids)
    # Tiny datasets stay in dev: a test claim requires at least three videos.
    if len(ids)<3:return {'train':[],'dev':ids,'test':[]}
    test=max(1,round(len(ids)*.2));dev=max(1,round(len(ids)*.2))
    return {'test':ids[:test],'dev':ids[test:test+dev],'train':ids[test+dev:]}
