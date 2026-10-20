"""Build honest, readable security guides and two submission PDFs from editable sources."""
from pathlib import Path
import argparse
import hashlib
import json
import re
from html import escape
from xml.sax.saxutils import escape as xml_escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib.pagesizes import A4
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics import renderPDF, renderSVG
import fitz

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
BUILD = ROOT / 'data/security-report-preview'
FONT = 'Arial' if Path('C:/Windows/Fonts/arial.ttf').exists() else 'Helvetica'
if FONT == 'Arial':
    pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))

DIAGRAMS = [
 ('security-overview', 'Where protection happens', [('Browser', 'Forms and memory-only access'), ('Server API', 'Identity, permissions and rules'), ('SQLite', 'Financial records and audit'), ('Private files', 'Originals, keys and backups'), ('Providers', 'Approved optional connections')], 'The API mediates access to records, private files and external providers.'),
 ('security-login', 'Password and authenticator', [('Password', 'Confirm the first factor'), ('Restricted step', 'No project access yet'), ('Authenticator', 'Enter a short-lived code'), ('Server checks', 'Expiry, replay and current role'), ('Full session', 'Access only after all checks')], 'MFA is implemented and has passed acceptance checks. The public demo stays exempt.'),
 ('security-authorization', 'Who may access this action?', [('Active account', 'Is this session still valid?'), ('Membership', 'Is this the right project?'), ('Current role', 'May this person do this?'), ('Record checks', 'Sources and approval match?'), ('Allowed action', 'Write once with audit evidence')], 'Project checks decide which records are accessible. Role checks decide which actions are permitted.'),
 ('security-upload', 'A document stays untrusted', [('Upload', 'Enforce a bounded request'), ('Validate', 'Check format and signature'), ('Private original', 'Generate the storage name'), ('Bounded parser', 'Limit pages, time and output'), ('Human review', 'Confirm procurement authority')], 'A valid file format does not make its contents true. Review and supporting records are still required.'),
 ('security-requests', 'Protect browser actions', [('Browser', 'Send the explicit marker'), ('Origin checks', 'Trusted origin and metadata'), ('Authentication', 'Check the server session'), ('Business rules', 'Check role, record and version'), ('Safe response', 'Return a typed result or error')], 'Origin and marker checks are implemented and tested. Authentication does not use cookies.'),
 ('security-secrets', 'Private keys through recovery', [('Generate', 'Use random local material'), ('Protect', 'Private files and permissions'), ('Use on server', 'Never expose provider keys'), ('Private backup', 'Copy consistent data and keys'), ('Isolated restore', 'Verify hashes; revoke sessions')], 'MFA uses a separate encryption key. Never put private backups or real setup QR codes in the submission.')
]

def wrap(text, width=22):
    import textwrap
    return textwrap.wrap(text, width=width)

def diagrams(verified):
    for name, title, nodes, caption in DIAGRAMS:
        overview=name=='security-overview'
        height=460 if overview else 330
        d=Drawing(1000, height)
        d.add(Rect(0,0,1000,height,fillColor=colors.HexColor('#f7f9f7'),strokeColor=None))
        d.add(String(26,height-39,title,fontName=FONT,fontSize=25,fillColor=colors.HexColor('#19343f')))
        for i,(heading,body) in enumerate(nodes):
            x,y=([(26,190),(250,190),(500,260),(500,100),(790,190)][i] if overview else (26+i*196,113))
            d.add(Rect(x,y,172,137,rx=10,fillColor=colors.HexColor('#e5efeb'),strokeColor=colors.HexColor('#91b8aa')))
            for j,line in enumerate(wrap(heading,17)):
                d.add(String(x+12,y+109-j*21,line,fontName=FONT,fontSize=18,fillColor=colors.HexColor('#19343f')))
            for j,line in enumerate(wrap(body,20)):
                d.add(String(x+12,y+58-j*18,line,fontName=FONT,fontSize=15,fillColor=colors.HexColor('#345751')))
            if i<4 and not overview:
                d.add(Line(x+176,180,x+190,180,strokeColor=colors.HexColor('#286e62'),strokeWidth=2))
                d.add(Polygon([x+190,180,x+184,184,x+184,176],fillColor=colors.HexColor('#286e62'),strokeColor=None))
        if overview:
            for x1,y1,x2,y2 in [(198,258,250,258),(422,280,500,328),(422,210,500,168),(422,248,790,248)]:
                d.add(Line(x1,y1,x2,y2,strokeColor=colors.HexColor('#286e62'),strokeWidth=2))
                d.add(Polygon([x2,y2,x2-8,y2+4,x2-8,y2-4],fillColor=colors.HexColor('#286e62'),strokeColor=None))
        note=caption
        if verified:
            note=note.replace('MFA is planned until the new acceptance evidence is recorded.','MFA has local acceptance evidence.').replace('New origin and marker checks are planned until tested.','Origin and marker checks have local acceptance evidence.')
        for j,line in enumerate(wrap(note,111)):
            d.add(String(26,75-j*20,line,fontName=FONT,fontSize=15,fillColor=colors.HexColor('#345751')))
        renderSVG.drawToFile(d,str(ASSETS/(name+'.svg')))
        svg=(ASSETS/(name+'.svg')).read_text()
        svg=svg.replace('<svg ', '<svg role="img" aria-label="'+escape(title,quote=True)+'" ',1)
        svg=svg.replace('<title>...</title>','<title>'+xml_escape(title)+'</title>').replace('<desc>...</desc>','<desc>'+xml_escape(note)+'</desc>')
        (ASSETS/(name+'.svg')).write_text(svg,encoding='utf-8')
        renderPDF.drawToFile(d,str(BUILD/(name+'.pdf')))
        with fitz.open(BUILD/(name+'.pdf')) as doc:doc[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(ASSETS/(name+'.png'))
        edges='\n  N0 --> N1\n  N1 --> N2\n  N1 --> N3\n  N1 --> N4\n' if overview else '\n  N0 --> N1 --> N2 --> N3 --> N4\n'
        (ASSETS/(name+'.mmd')).write_text('flowchart LR\n'+'\n'.join(f'  N{i}["{heading}: {body}"]' for i,(heading,body) in enumerate(nodes))+edges,encoding='utf-8')

def append_section(path,section):
    marker='\n<!-- security-upgrade-start -->'
    text=path.read_text(encoding='utf-8').split(marker)[0].rstrip()
    path.write_text(text+marker+'\n'+section+'\n',encoding='utf-8')

def pdf(source,target):
    styles=getSampleStyleSheet()
    for st in styles.byName.values():st.fontName=FONT
    styles['Normal'].fontSize=10;styles['Normal'].leading=14;styles['Normal'].spaceAfter=7
    styles['Heading1'].fontSize=22;styles['Heading1'].leading=27
    styles['Heading2'].fontSize=15;styles['Heading2'].leading=20
    styles['Heading3'].fontSize=12;styles['Heading3'].leading=16
    for name in ('Heading1','Heading2','Heading3'):
        styles[name].textColor=colors.HexColor('#19343f')
    styles.add(ParagraphStyle('Cell',fontName=FONT,fontSize=8.5,leading=11,alignment=TA_LEFT))
    def rich(text):
        links=[]
        def link(match):
            label,url=match.groups()
            if not url.startswith(('https://','http://')):
                relative,sep,anchor=url.partition('#')
                resolved=(source.parent/relative).resolve().relative_to(ROOT).as_posix()
                url='https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai/blob/main/'+resolved+(sep+anchor if sep else '')
            links.append('<link href="'+escape(url,quote=True)+'" color="#286e62">'+xml_escape(label)+'</link>')
            return f'LINKPLACEHOLDER{len(links)-1}END'
        text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,text)
        text=xml_escape(text)
        text=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
        text=re.sub(r'`([^`]+)`',r'\1',text)
        for i,value in enumerate(links):text=text.replace(f'LINKPLACEHOLDER{i}END',value)
        return text.replace('→',' - ').replace('–','-').replace('—','-')
    lines=source.read_text(encoding='utf-8').splitlines();story=[];i=0;code=False
    while i<len(lines):
        line=lines[i].strip();i+=1
        if line.startswith('```'):code=not code;continue
        if not line or line.startswith('<!--'):continue
        if re.match(r'^### [A-Z][0-9]{2} - ',line) or line in ('## Important distinctions','## Interfaces and operating rules'):
            important=line.startswith('## ')
            group=[Paragraph(rich(line[3:] if important else line[4:]),styles['Heading2' if important else 'Heading3'])]
            while i<len(lines) and not lines[i].lstrip().startswith('#'):
                value=lines[i].strip();i+=1
                if value:group.append(Paragraph(rich(value),styles['Normal']))
            story.append(KeepTogether(group));continue
        if line.startswith('|'):
            rows=[line]
            while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
            cells=[[Paragraph(rich(v.strip()),styles['Cell']) for v in row.strip('|').split('|')] for row in rows if not re.fullmatch(r'[|\s:\-]+',row)]
            table=Table(cells,colWidths=[(A4[0]-84)/len(cells[0])]*len(cells[0]),repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5efeb')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#b5c8c0')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
            if source.name=='project-overview.md':
                heading=[story.pop()] if story and isinstance(story[-1],Paragraph) and story[-1].style.name.startswith('Heading') else []
                story.append(KeepTogether([*heading,table,Spacer(1,10)]))
            else:
                story.extend([table,Spacer(1,10)])
            continue
        image=re.match(r'!\[([^]]*)\]\(([^)]+)\)',line)
        if image:
            path=source.parent/image[2];path=path.with_suffix('.png') if path.suffix=='.svg' else path
            if path.exists():
                from PIL import Image as PILImage
                w,h=PILImage.open(path).size
                group=[Image(str(path),width=A4[0]-84,height=(A4[0]-84)*h/w),Paragraph(rich(image[1]),styles['Cell'])]
                j=i
                while j<len(lines) and not lines[j].strip():j+=1
                if j<len(lines) and not lines[j].lstrip().startswith(('#','![','|','<!--')):
                    group.append(Paragraph(rich(lines[j].strip()),styles['Normal']));i=j+1
                group.append(Spacer(1,12));story.append(KeepTogether(group))
            continue
        level=len(line)-len(line.lstrip('#'))
        style=styles.get(f'Heading{min(level,3)}') if level else styles['Normal']
        text=line[level:].strip() if level else line
        if text.startswith('- '):text='- '+text[2:]
        story.append(Paragraph(rich(text),style))
    def footer(canvas,document):
        canvas.setFont(FONT,8);canvas.setFillColor(colors.HexColor('#526971'));canvas.drawString(42,24,'BuildTrust AI | Local sandbox | Security status and limits are explicit');canvas.drawRightString(A4[0]-42,24,str(document.page))
    SimpleDocTemplate(str(target),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=42,title=source.stem.replace('-',' ').title(),author='BuildTrust AI Team').build(story,onFirstPage=footer,onLaterPages=footer)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verified-receipt',type=Path,required=True);args=parser.parse_args()
    BUILD.mkdir(parents=True,exist_ok=True)
    data=json.loads((ASSETS/'security-controls.json').read_text());verified=False
    if args.verified_receipt:
        receipt=json.loads(args.verified_receipt.read_text());assert receipt['passed'];assert set(receipt['verified_controls'])=={r[0] for r in data['controls'] if r[0] not in ('A06','C02')};verified=True
    diagrams(verified)
    summary='Security hardening is implemented. The recorded local security checks and the October 20 hosted Windows/Linux run passed. The local suite passed 251 backend tests, 10 frontend tests, 20 browser workflows and all eight original HTTP scenarios. Each hosted runner passed 250 backend tests and skipped one optional OCR model check. [Read the actual hosted results](https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai/actions/runs/39419213954).'
    section='## The 19-control security improvement checklist\n\n'+summary+'\n\nCurrent labels: **verified**, **deferred** and **not applicable**. Seventeen controls are verified. Native database RLS is deferred and incoming webhooks are not applicable. The previous 20-item review remains separate.\n\n'
    section+='## Read the trust boundaries\n\n'
    for name,title,nodes,caption in DIAGRAMS:
        section+=f'![{title}](assets/{name}.png)\n\n{caption if not verified else caption.replace("MFA is planned until the new acceptance evidence is recorded.","MFA has local acceptance evidence.").replace("New origin and marker checks are planned until tested.","Origin and marker checks have local acceptance evidence.")}\n\n'
    for ident,title,purpose,status,current,work in data['controls']:
        shown='verified' if verified and ident not in ('A06','C02') else status
        facts=receipt['controls'][ident] if verified else None
        current=facts['implementation'] if facts else current
        work=facts['limitation'] if facts else work
        evidence=facts['evidence'] if facts else 'Recorded baseline only; new acceptance is pending.'
        section+=f'### {ident} - {title}\n\n**Purpose:** {purpose}\n\n**Status:** {shown}.\n\n**Current implementation:** {current}\n\n**Evidence:** {evidence}\n\n**Boundary:** {work}\n\n'
    section+='## Important distinctions\n\n- XSS means content runs as a script. CSRF means a different website tries to submit an action. They require different controls.\n- Project isolation is enforced by this application. Native database RLS remains deferred while SQLite is used.\n- Incoming webhooks stay disabled. No real payment callback or signature-verification claim is made.\n- Private Admin and Finance accounts will require MFA; the four marked public-demo accounts keep their README passwords and simple login.\n- Logs and dependency lockfiles must exclude private values. A dependency scan is not an independent security assessment.\n\nSources: [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [OWASP MFA](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html), [OWASP SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [PyOTP](https://pyauth.github.io/pyotp/).\n'
    if verified:section=section.replace('will require MFA','require MFA')
    append_section(ROOT/'docs/security-self-assessment.md',section)
    technical='## Implemented security architecture\n\n'+summary+'\n\n'
    technical+='The current application uses memory-only bearer tokens and revocable server sessions. The next migration adds encrypted MFA factors, restricted challenges, hashed recovery codes and session assurance. Planned MFA is not part of the baseline evidence.\n\n' if not verified else 'MFA adds encrypted factors, restricted challenges, hashed recovery codes and server-checked session assurance. Current evidence identifies the tested revision and results.\n\n'
    for name,title,nodes,caption in DIAGRAMS:
        technical+=f'![{title}](assets/{name}.png)\n\n'+(caption if name=='security-overview' else ' -> '.join(n[0] for n in nodes)+'.')+'\n\n'
    technical+='## Interfaces and operating rules\n\n- Mutating requests will require X-BuildTrust-Request: 1 and explicit origin checks. No authentication cookies are introduced.\n- MFA challenges are restricted to setup or verification; they must never authorize financial actions.\n- TOTP uses six digits and 30-second periods. Used periods and recovery codes cannot be replayed.\n- A separate private key encrypts MFA factors. Backup and restore must include it; missing keys fail closed.\n- Only the local owner may reset MFA. Password recovery alone cannot remove it.\n- SQLite keeps project isolation in server queries. Native PostgreSQL RLS is a separate deferred release.\n- No incoming webhook receiver is enabled.\n- The public-demo credentials in README remain unchanged and exempt from MFA.\n\nSee the [19 distinct control entries](security-self-assessment.md#the-19-control-security-improvement-checklist) and [recorded verification](completion-verification.md).\n'
    if verified:technical=technical.replace('will require','require')
    append_section(ROOT/'docs/technical-documentation.md',technical)
    outputs=[]
    for source,name in [('security-self-assessment.md','BuildTrustAI_Security_Self_Assessment.pdf'),('technical-documentation.md','BuildTrustAI_Technical_Documentation.pdf'),('project-overview.md','BuildTrustAI_Project_Overview.pdf')]:
        target=ROOT/'submission'/name;pdf(ROOT/'docs'/source,target)
        with fitz.open(target) as doc:
            text=''.join(p.get_text() for p in doc);assert len(text)>2000
            for i,p in enumerate(doc):p.get_pixmap(matrix=fitz.Matrix(1,1)).save(BUILD/(target.stem+f'-{i+1:02}.png'))
            outputs.append({'file':name,'pages':len(doc),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'text_extraction_passed':True,'verified_upgrade':verified})
    (BUILD/'result.json').write_text(json.dumps({'outputs':outputs},indent=2)+'\n');print(json.dumps(outputs,indent=2))

if __name__=='__main__':main()
