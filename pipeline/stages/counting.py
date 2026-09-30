from collections import Counter
from statistics import mean, median

def side(point, a, b):
    return (b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])

def crossing(p, q, a, b):
    """Finite line intersection; a stationary/on-line point never creates a hit."""
    s1, s2 = side(p,a,b), side(q,a,b)
    if s1*s2 >= 0: return None
    if side(a,p,q)*side(b,p,q) > 0: return None
    return 'A→B' if s1<0 else 'B→A'

def count_tracks(tracks, lines, fps):
    crossings=[]
    for track in tracks:
        for line in lines:
            seen=set()
            for previous,current in zip(track['frames'],track['frames'][1:]):
                def centre(f):
                    x1,y1,x2,y2=f['box']; return ((x1+x2)/2,y2)
                direction=crossing(centre(previous),centre(current),line['start'],line['end'])
                if direction and direction not in seen:
                    seen.add(direction)
                    crossings.append({'track_id':track['track_id'],'class':track['class'],'line_id':line['id'],'direction':direction,'frame':current['frame'],'video_time_s':current['frame']/fps,'minute':int(current['frame']/fps//60),'source':'real','expires_at':track['expires_at']})
    values=[t['dwell_s'] for t in tracks]
    return {'lines':lines,'crossings':crossings,'totals':dict(Counter(c['class'] for c in crossings)), 'direction_totals':dict(Counter(c['direction'] for c in crossings)), 'unique_tracks':len(tracks),'track_classes':dict(Counter(t['class'] for t in tracks)), 'dwell':{'mean_s':mean(values) if values else None,'median_s':median(values) if values else None,'values_s':values}}
