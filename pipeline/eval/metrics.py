import math,re
from collections import defaultdict,Counter
def normal(text):return re.sub(r'[\s-]','',str(text).upper())
def edit_distance(a,b):
    row=list(range(len(b)+1))
    for i,c in enumerate(a):
        new=[i+1]
        for j,d in enumerate(b):new.append(min(new[-1]+1,row[j+1]+1,row[j]+(c!=d)))
        row=new
    return row[-1]
def wilson(correct,n):
    if not n:return [0.,1.]
    z=1.959963984540054;p=correct/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;spread=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,mid-spread),min(1,mid+spread)]
def character_confusions(expected,predicted):
    a,b=normal(expected),normal(predicted);matrix=[list(range(len(b)+1))]
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):row.append(min(row[-1]+1,matrix[-1][j]+1,matrix[-1][j-1]+(x!=y)))
        matrix.append(row)
    i,j=len(a),len(b);counts=Counter()
    while i or j:
        if i and j and matrix[i][j]==matrix[i-1][j-1]+(a[i-1]!=b[j-1]):
            if a[i-1]!=b[j-1]:counts[f'{a[i-1]}→{b[j-1]}']+=1
            i-=1;j-=1
        elif i and matrix[i][j]==matrix[i-1][j]+1:counts[f'{a[i-1]}→∅']+=1;i-=1
        else:counts[f'∅→{b[j-1]}']+=1;j-=1
    return counts
def accuracy(rows):
    n=len(rows);correct=sum(bool(r['prediction']) and normal(r['prediction'])==normal(r['plate']) for r in rows)
    return {'value':correct/n if n else None,'ci95':wilson(correct,n),'n':n,'correct':correct}
def compute(rows,min_height=25):
    eligible=[r for r in rows if str(r['readable']).lower() in ('true','1','yes') and float(r.get('plate_height_px') or 0)>=min_height]
    accepted=[r for r in rows if r['prediction']];den=sum(len(normal(r['plate'])) for r in rows);groups=defaultdict(list)
    for r in rows:groups[r.get('condition','unspecified')].append(r)
    errors=[]
    for r in rows:
        if not r['prediction'] or normal(r['prediction'])!=normal(r['plate']):errors.append({'clip_id':r['clip_id'],'track_id':int(r['track_id']),'expected':normal(r['plate']),'predicted':r['prediction'],'category':'abstention / no plate read' if not r['prediction'] else 'OCR character confusion'})
    second=[r for r in rows if r.get('second_plate')]
    confusions=Counter()
    for r in rows:confusions.update(character_confusions(r['plate'],r['prediction']))
    return {'confusion_matrix':dict(confusions),'n_tracks':len(rows),'n_eligible':len(eligible),'plate_accuracy_readable':accuracy(eligible) if eligible else None,'plate_accuracy_all':accuracy(rows) if rows else None,'cer':sum(edit_distance(normal(r['plate']),normal(r['prediction'])) for r in rows)/den if den else None,'coverage':len(accepted)/len(rows) if rows else None,'selective_accuracy':accuracy(accepted) if accepted else None,'by_condition':{k:accuracy(v) for k,v in groups.items()},'coverage_curve':[{'threshold':t/10,'coverage':len(sub)/len(rows) if rows else 0,'accuracy':accuracy(sub)['value']} for t in range(5,11) for sub in [[r for r in rows if r['prediction'] and r['confidence']>=t/10]]],'error_cases':errors[:20],'error_categories':dict(Counter(e['category'] for e in errors)),'inter_labeller_agreement':sum(normal(r['plate'])==normal(r['second_plate']) for r in second)/len(second) if second else None,'by_plate_size':{label:accuracy([r for r in rows if low<=float(r.get('plate_height_px') or 0)<high]) for label,low,high in [('under25',0,25),('25to49',25,50),('50plus',50,float('inf'))]}}

