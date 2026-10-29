"""Deterministic sheet planning; all bounds include the complete cut/bleed.

Homogeneous batches retain the approved legacy layout. Mixed batches use
conservative square bounds for circles and a 2 mm gap, then center the complete
group on each sheet while keeping at least 2 mm outer clearance.
"""
from engine import DPI, PAGE, page_positions, template_info

GAP = round(2 / 25.4 * DPI)
MARGIN = GAP


def _contains(a, b):
    x,y,w,h=a;xx,yy,ww,hh=b
    return x<=xx and y<=yy and x+w>=xx+ww and y+h>=yy+hh


def _split(free, used):
    ux,uy,uw,uh=used; result=[]
    for x,y,w,h in free:
        if ux>=x+w or ux+uw<=x or uy>=y+h or uy+uh<=y:
            result.append((x,y,w,h));continue
        if ux>x:result.append((x,y,ux-x,h))
        if ux+uw<x+w:result.append((ux+uw,y,x+w-ux-uw,h))
        if uy>y:result.append((x,y,w,uy-y))
        if uy+uh<y+h:result.append((x,uy+uh,w,y+h-uy-uh))
    unique=list(dict.fromkeys(result))
    return [r for i,r in enumerate(unique) if not any(i!=j and _contains(other,r) for j,other in enumerate(unique))]


def plan_pages(items, default='square'):
    if not isinstance(items,list) or not 1<=len(items)<=100 or any(not isinstance(item,dict) for item in items):
        raise ValueError('Selecione entre 1 e 100 imagens.')
    keys=[item.get('template',default) for item in items]
    specs=[template_info(key) for key in keys]
    if len(set(keys))==1:
        key=keys[0];capacity=specs[0]['capacity']
        return [dict(indices=list(range(start,min(start+capacity,len(items)))),
                     positions=page_positions(min(capacity,len(items)-start),key))
                for start in range(0,len(items),capacity)]
    pages=[]
    for index in sorted(range(len(items)),key=lambda i:(-specs[i]['cut_px'],i)):
        size=specs[index]['cut_px'];padded=size+GAP;candidates=[]
        for page_no,page in enumerate(pages):
            for x,y,w,h in page['free']:
                if padded<=w and padded<=h:
                    candidates.append(((min(w-padded,h-padded),max(w-padded,h-padded),page_no,y,x),page_no,x,y))
        if not candidates:
            pages.append(dict(indices=[],positions=[],free=[(MARGIN,MARGIN,PAGE[0]-2*MARGIN+GAP,PAGE[1]-2*MARGIN+GAP)]))
            page_no=len(pages)-1;x=y=MARGIN
        else:_,page_no,x,y=min(candidates)
        page=pages[page_no];page['indices'].append(index);page['positions'].append((x,y))
        page['free']=_split(page['free'],(x,y,padded,padded))
    result=[]
    for page in pages:
        positions=dict(zip(page['indices'],page['positions']));indices=sorted(page['indices'])
        if len({keys[i] for i in indices})==1:
            points=page_positions(len(indices),keys[indices[0]])
        else:
            # Translate the complete packed group; never resize tiles or change
            # their relative spacing. Exclude the packer's trailing gap from
            # the bounds so the actual cut areas have balanced outer margins.
            left=min(positions[i][0] for i in indices)
            top=min(positions[i][1] for i in indices)
            right=max(positions[i][0]+specs[i]['cut_px'] for i in indices)
            bottom=max(positions[i][1]+specs[i]['cut_px'] for i in indices)
            dx=(PAGE[0]-(right-left))//2-left
            dy=(PAGE[1]-(bottom-top))//2-top
            points=[(positions[i][0]+dx,positions[i][1]+dy) for i in indices]
        result.append(dict(indices=indices,positions=points))
    return result


def compose_sheet(tiles, positions):
    from PIL import Image
    page=Image.new('RGB',PAGE,'white')
    try:
        for tile,position in zip(tiles,positions):page.paste(tile,tuple(position))
        return page
    except Exception:
        page.close();raise
