"""Rebuild curated starter entries from locally downloaded official statute texts.
PDF extraction is a build-time operation; the running app needs no dependencies.
"""
from pathlib import Path
import hashlib
import json
import re

DATA=Path(__file__).resolve().parents[1]/'data'
SPECS=[]


def add(file,number,heading,domain,issue,meaning,when,limits,questions,elements,keywords=None):
    SPECS.append(dict(file=file,number=number,heading=heading,domain=domain,issue=issue,
        plain_explanation=meaning,when_to_use=when,do_not_use_when=limits,helpful_material=questions,
        elements=elements,keywords=keywords))


add('food',26,'Responsibilities of the Food business operator','food',
    'Did a food business fail its food-safety responsibilities?',
    'Food businesses must ensure food meets the Act and applicable rules within the business activities they control. The provision addresses unsafe, misbranded, substandard and other prohibited food.',
    'Start here for an account of contaminated, spoiled, adulterated or otherwise non-compliant food supplied by a food business.',
    'Disliking the taste or becoming unwell after a meal does not by itself establish a breach or prove which food caused illness. Identify the actual problem and applicable standard.',
    'What was the food, where and when was it supplied, and what did you observe? Keep packaging, order details and photographs if available. Do not delay needed medical care to obtain proof.',
    ['Food supplied by an identifiable business','Reported safety or compliance concern','Relevant business activity and control'])
add('food',40,'Purchaser may have food analysed','food',
    'Would the purchaser-analysis route help clarify the food concern?',
    'This section provides a purchaser route to analysis by a Food Analyst, with statutory conditions including notice to the business at purchase and prescribed fees. It also addresses the analyst report and follow-up.',
    'Explore this when a person asks about formal food analysis. Ask the food-safety authority how the statutory conditions and current sampling rules apply to an already-purchased item.',
    'It is not a promise that any private laboratory test qualifies or that testing is mandatory before raising a concern. Do not tell an already-past purchaser they can retrospectively satisfy the notice condition.',
    'When was it purchased, is any sample available, and was analysis mentioned at purchase? Ask the relevant authority about safe preservation and proper sampling.',
    ['Purchaser and identifiable food','Statutory notice-at-purchase condition','Proper analyst and current procedure'])
add('food',59,'Punishment for unsafe food','food',
    'Do the facts raise an unsafe-food issue rather than only a quality complaint?',
    'This provision concerns manufacture for sale, storage, sale, distribution or import of unsafe food for human consumption. Injury and causation can affect the legal assessment.',
    'Consider it if the reported facts suggest unsafe food. Food-safety findings and the circumstances must be assessed before alleging an established offence.',
    'Illness after eating, an expired label, or a photograph alone does not automatically establish unsafe food or causation. This source is the original 2006 text; current penalties and amendments must be checked separately.',
    'What was wrong with the food, who supplied it, when were symptoms noticed, and has a clinician or authority assessed the issue? Medical care should not wait for legal research.',
    ['Food intended for human consumption','Specified supply-chain conduct','Whether food was unsafe','Injury and causal link if alleged'])
add('food',65,'Compensation in case','food',
    'Is there an injury linked to food for which compensation could be considered?',
    'This provision addresses compensation directed by the adjudicating officer or court where supplied food causes injury or death. It does not guarantee an award on an allegation alone.',
    'Consider it as a potential later route when injury and its connection to the supplied food emerge. Keep the safety complaint and the compensation question distinct.',
    'Do not promise amounts or deadlines from this original enactment snapshot. A refund request without injury does not automatically meet this provision’s conditions.',
    'Clarify any medical assessment, treatment expenses and chronology. Note other possible causes honestly; preserve records you already have.',
    ['Specified food-supply conduct','Injury or death','Connection between the food and harm','Assessment by the competent authority'])

add('consumer',38,'','consumer','How would an admitted consumer complaint be considered?',
    'This section describes the procedure after admission of a complaint, including responses, evidence and testing where required for an alleged goods defect.',
    'Use it to explain a potential later procedural stage after filing or when the other side disputes the complaint.',
    'Do not treat filing as automatic admission, assume every case needs a lab test, or invent a hearing timetable. Current procedural rules still need checking.',
    'Has a complaint been filed or admitted? What order or notice was received, and what is the next date recorded in it?',
    ['Complaint stage','Goods or service issue','Opposite party response','Evidence and directions in the actual proceeding'])
add('consumer',69,'','consumer','Is the consumer complaint within the statutory filing period?',
    'The section states a two-year period from accrual of the cause of action. It also allows consideration of a delayed complaint on sufficient cause with recorded reasons.',
    'Check this early when considering a consumer complaint, especially if events happened some time ago. Accrual and any condonation need factual and legal review.',
    'Do not calculate a final filing date from the purchase date alone or promise that delay will be excused. A recent message does not automatically restart time.',
    'List purchase, problem, refusal and complaint dates, and any reason for delay. Obtain timely advice if a filing deadline may be close.',
    ['Accrual of cause of action','Date of filing','Any delay and sufficient cause'])
add('consumer','2-47','unfair trade practice','consumer','Was there a specifically described unfair trade practice?',
    'This definition lists forms of unfair trade practice, including specified false representations and other listed conduct. The relevant limb and facts must be identified.',
    'Consider it for an account of misleading claims or another listed practice, alongside the appropriate goods or service provisions.',
    'A disagreement, unsuccessful service or delayed refund is not automatically every listed unfair practice. Avoid labelling ordinary non-performance as established fraud.',
    'What exactly was represented, by whom, and how did it differ from what was supplied? Preserve the advert or messages if available.',
    ['Specific representation or listed conduct','Relevant statutory limb','Difference between the promise and reported events'])

add('specific-relief',5,'Recovery of specific immovable property','property','Who is entitled to possession of the immovable property?',
    'A person entitled to possession of specific immovable property may recover it through the civil procedure provided by law.',
    'Use it as a starting point for a claim to recover land or a building when entitlement and possession need assessment.',
    'A deed, tax record or an allegation alone does not settle every title or possession dispute. Tenancy, inheritance, land and state-specific rules may change the route.',
    'Which state is the property in, who possesses it now, what right is claimed, and what documents or prior orders exist?',
    ['Identifiable immovable property','Claimed entitlement to possession','Current possession and applicable civil route'])
add('specific-relief',6,'Suit by person dispossessed','property','Was a person dispossessed without consent otherwise than through due process?',
    'This provision provides a possessory suit subject to its conditions, including a six-month window from dispossession and exclusion of suits against the Government. It does not finally determine title.',
    'Check promptly when someone reports being forcibly or unlawfully removed from possession. Confirm the dispossession date and whether this remedy fits.',
    'Do not use it as a general title declaration, assume it applies against Government, or ignore its time limit. Other routes may need assessment if its conditions are not met.',
    'Who was in possession, when and how was possession lost, was there consent or a court process, and is Government the opposing party?',
    ['Previous possession','Dispossession without consent otherwise than due course of law','Date and six-month condition','Government exclusion'])
add('specific-relief',34,'Discretion of court as to declaration','property','Is a legal status or property right being denied?',
    'A court may declare an entitlement to legal character or property rights in the circumstances specified. The proviso restricts a bare declaration where further available relief is omitted.',
    'Explore it where title or a claimed property right is genuinely disputed, considering possession and any consequential relief together.',
    'Do not assume a bare declaration alone is sufficient when possession or other further relief is required. The provision does not itself establish ownership.',
    'What right is denied, on what basis, who is in possession, and what outcome beyond a declaration is needed?',
    ['Claimed legal character or property right','Denial by the opposing party','Need for further consequential relief'])
add('specific-relief',38,'Perpetual injunction when granted','property','Is there a threatened or actual invasion of a property right or obligation?',
    'A perpetual injunction may be granted in the statutory circumstances to prevent breach of an obligation or invasion of a property right. It is a discretionary remedy decided on the merits.',
    'Explore it for threatened interference with a claimed right, while checking title, possession, the statutory conditions and any other necessary relief.',
    'It is not the same as an immediately granted temporary order. A person out of possession or with disputed title may need additional relief; do not promise an injunction.',
    'What interference is happening, who possesses the property, what right supports the claim, and is urgent interim advice needed?',
    ['Relevant right or obligation','Actual or threatened invasion','Statutory grounds and adequacy of other relief'])
add('bns',329,'','property','Do the reported acts meet criminal-trespass conditions?',
    'Criminal trespass requires entry or unlawful remaining with the specified intent, such as committing an offence or intimidating, insulting or annoying a person in possession. House-trespass has additional setting requirements.',
    'Consider it only when the account raises the entry/remaining and intent elements, alongside any civil possession issues.',
    'Do not convert every boundary, title, landlord or ownership dispute into a criminal allegation. Disputed entry alone does not establish all elements.',
    'Who was in possession, what entry or remaining occurred, and what facts suggest the required intent? Distinguish observed words or acts from assumptions.',
    ['Possession of another','Entry or unlawful remaining','Specified intent','Setting if house-trespass is alleged'],
    ['trespass','broke in','intimidate','threatened','encroachment','entered my land'])

add('bns',63,'','sexual','Could the reported act fall within the statutory definition of rape?',
    'The definition combines specified sexual acts with listed circumstances concerning will, consent, age or ability to communicate consent. It contains gendered statutory wording, explanations and exceptions. Lack of physical resistance alone is not consent.',
    'Use this as a conditional legal starting point for a reported rape or non-consensual sexual act. Check incident date, age and statutory conditions without requiring a graphic retelling.',
    'Do not infer consent from silence, lack of injury, relationship or delayed reporting. Not every sexual assault has the same legal definition. Exceptions and other applicable protections need qualified review.',
    'Is the affected person safe and able to seek care? What was their age at the incident, approximate date and state? Broad descriptions are enough for this initial stage; identifying or graphic details are not required.',
    ['Act within the statutory definition','Relevant will or consent circumstance','Age and other statutory conditions','Incident date and any applicable exception'])
add('bns',64,'','sexual','Which punishment provision may follow if rape is legally established?',
    'This section provides punishment for rape, including specified aggravated circumstances. It follows legal determination of the relevant offence and facts.',
    'Consider it after identifying the possible definition and facts. A general initial account does not establish an aggravated category or predict a sentence.',
    'Do not quote a guaranteed sentence or infer an aggravated circumstance, guilt or outcome from a report alone. Special age-related provisions may require further research.',
    'A legal professional should assess any relevant relationship of authority, vulnerability or other statutory circumstance from the minimum necessary facts.',
    ['Possible rape definition','Relevant statutory category','Facts required for any specified circumstance'])
add('bns',74,'','sexual','Could the reported assault or criminal force meet this provision’s conditions?',
    'This section concerns assault or criminal force against a woman with the specified intent or knowledge concerning outraging modesty. It is distinct from the rape definition.',
    'Explore it where the description concerns unwanted assault or force and the statutory intent/knowledge and gender conditions may be relevant.',
    'Do not assume all unwanted contact is legally identical or that this section substitutes for a more specific applicable provision. For a child, POCSO also needs checking.',
    'Only share what you feel able to share: the broad nature of contact, age, date and context. Missing recordings or injuries does not prevent an initial legal discussion.',
    ['Assault or criminal force','Statutory gender condition','Specified intent or knowledge'])
add('bns',75,'','sexual','Does the account describe a listed form of sexual harassment?',
    'This section lists forms of sexual harassment, including specified unwelcome physical conduct, sexual demands, pornography against a woman’s will and sexually coloured remarks, within its statutory wording.',
    'Explore the relevant listed act when the description concerns sexual harassment. Workplace-specific procedures or other statutes may also need separate research.',
    'Do not label every workplace disagreement as sexual harassment or assume the same statute covers every person and act. Check age and other potentially applicable protection laws.',
    'What broad type of unwelcome conduct was reported, when, in what setting, and what outcome or immediate support is wanted?',
    ['Conduct within a listed category','Applicable statutory conditions','Context and any additional protection route'])

add('pocso','2-1-d','child','child','Was the affected person below eighteen at the time?',
    'For this Act, a child is a person below eighteen years of age. Age at the alleged incident is the important starting question.',
    'Check this when a sexual-offence concern may involve a child; the Act’s protections are not limited to girls.',
    'Do not infer age from school class, appearance or current age. If age is unknown, ask gently and keep child-related sections conditional.',
    'Ask only the age or approximate age at the incident initially. Do not request a child’s name, address, photograph or explicit material.',
    ['Age below eighteen at the incident'])
add('pocso',3,'Penetrative sexual assault','child','Could the alleged act fall within the child-protection definition of penetrative sexual assault?',
    'This section defines specified penetrative sexual acts involving a child. It must be read with the child definition and relevant statutory provisions.',
    'Consider it conditionally where the account broadly indicates a penetrative sexual act and age below eighteen. A graphic retelling is not needed for initial guidance.',
    'Do not infer penetration from a vague reference to touching or demand explicit descriptions. A different POCSO provision may be relevant to non-penetrative conduct.',
    'Prioritise current safety, care, age at the incident and a broad non-graphic description. Seek trained child-protection assistance rather than repeatedly questioning the child.',
    ['Child at the relevant time','Act within the statutory definition'])
add('pocso',7,'Sexual assault','child','Could there have been physical contact with sexual intent without penetration?',
    'This section addresses specified touching and other acts with sexual intent involving physical contact without penetration. The sexual-intent and contact requirements matter.',
    'Consider it for a child’s report of inappropriate sexual touching. Contact through clothing is not excluded solely because it was not skin-to-skin.',
    'Do not infer sexual intent from every ordinary touch, or treat absence of skin-to-skin contact as an automatic exclusion. Consider a different provision if penetration is reported.',
    'Use a broad description already shared; do not prompt for repeated or graphic details. Clarify age and what immediate support is needed.',
    ['Child at the incident','Physical contact without penetration','Sexual intent'])
add('pocso',19,'Reporting of offences','child','Does a child-protection concern trigger the reporting provision?',
    'The section requires information about apprehended or known offences under the Act to be provided to the Special Juvenile Police Unit or local police. It includes child-friendly recording and protection provisions.',
    'Explain this reporting route when a possible POCSO concern is raised. Do not make reporting guidance depend on having CCTV, a medical report or a completed proof file.',
    'The app does not report automatically and cannot promise confidentiality against statutory reporting duties. Do not encourage private settlement or delaying urgent care while collecting evidence.',
    'Prioritise whether the child is currently safe, age at the incident and access to a trusted safe adult or trained professional. Avoid unnecessary identifying information in the app.',
    ['Apprehension or knowledge of a possible POCSO offence','Information to the statutory reporting authority','Child-friendly handling'])
add('pocso',24,'Reco','child','How should a child’s statement be handled?',
    'This section addresses recording a child’s statement, including the child’s choice of place, specified officer safeguards, avoiding contact with the accused, no overnight police-station detention and identity protection.',
    'Use it to explain protective features of statement recording if a child-related complaint is progressing.',
    'Do not conduct a simulated cross-examination of the child or promise every procedural detail without checking current rules. Preserve the child’s own words without coaching.',
    'A trusted safe adult and trained child-protection professional can help explain the process. Avoid making the child repeat the account unnecessarily.',
    ['Child’s statement','Choice of place and officer safeguards','Protection from accused contact','Privacy and overnight-detention safeguard'])
add('pocso',27,'Medical examination of a child','child','What child-specific safeguards concern medical examination?',
    'This section provides for medical examination of a child with specified safeguards, including examination even when an FIR or complaint has not been registered, and support-person provisions.',
    'Use it to explain that needed care should not be postponed for an FIR and that child-specific examination protections must be considered.',
    'Do not offer a forensic diagnosis, promise examination findings or advise self-examination or collection of intimate material. A qualified clinician must provide care.',
    'Ask only whether urgent care or help reaching a clinician is needed. A trusted safe support person may assist within the statutory safeguards.',
    ['Child needing medical examination','No prior-FIR prerequisite in the provision','Specified examination and support-person safeguards'])

FILES={
    'food':('Food Safety and Standards Act, 2006','https://www.fssai.gov.in/upload/uploadfiles/files/FOOD-ACT.pdf','Original 2006 enactment; later amendments, current penalties and regulations must be checked'),
    'consumer':('Consumer Protection Act, 2019','https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf','2019 enactment; current rules and amendments require checking'),
    'specific-relief':('Specific Relief Act, 1963','https://www.indiacode.nic.in/bitstream/123456789/1583/7/A1963-47.pdf','India Code publication with amendments noted; state and other applicable rules require checking'),
    'bns':('Bharatiya Nyaya Sanhita, 2023','https://www.mha.gov.in/files/documents/250883_english01042024.pdf','2023 enacted text; incident-date and later-amendment checks are required'),
    'pocso':('Protection of Children from Sexual Offences Act, 2012','https://www.indiacode.nic.in/bitstream/123456789/2079/1/AA2012-32.pdf','India Code text with amendment notes; incident-date and current-rule checks are required')}
WORDS={
    'food':['food','meal','restaurant','contaminated','poisoning','adulterated','expired','unsafe food','milk','food safety','खाना','भोजन'],
    'consumer':['consumer','refund','defective','seller','purchase','bought','warranty','service','complaint','misleading','उपभोक्ता'],
    'property':['land','property','possession','title','landlord','tenant','evicted','dispossessed','forcibly removed','kicked out','inheritance','inherited house','boundary','encroachment','trespass','entered my property','entered my house','unlawful entry','जमीन','कब्जा'],
    'sexual':['rape','raped','sexual assault','sexual','sexually','molested','unwanted touching','बलात्कार','यौन'],
    'child':['child','minor','daughter','son','underage','sexual','sexually','molested','बच्चा','बच्ची']}
FOLLOW_UP_IDS={'fssa-40','fssa-65','cpa-38'}

# Keep search tied to the particular issue. Broad subject terms belong on
# definitions; otherwise a rape account can incorrectly surface harassment
# and procedural sections as if they describe the same offence.
KEYWORD_OVERRIDES={
    'cpa-38':['consumer commission admitted complaint','consumer commission procedure','consumer complaint evidence stage'],
    'cpa-69':['consumer complaint limitation','consumer complaint filed late','cause of action consumer complaint','consumer complaint deadline'],
    'cpa-2-47':['unfair trade practice','misleading advertisement','false representation seller','fake discount','hidden terms'],
    'bns-63':['rape','raped','non-consensual intercourse','forced sex','बलात्कार'],
    'bns-64':['rape','raped','aggravated rape','gang rape','बलात्कार'],
    'bns-74':['molested','groped','unwanted sexual touch','assaulted me','criminal force woman'],
    'bns-75':['sexual harassment','sexual remarks','sexual favours','unwelcome sexual advances','pornography shown'],
    'pocso-2-1-d':['child','minor','under 18','under eighteen','daughter','son','बच्चा','बच्ची'],
    'pocso-3':['child rape','rape of a child','daughter was raped','minor rape','penetrative sexual assault child','penetration child','sexual assault child','बच्चे से बलात्कार'],
    'pocso-7':['child touching','sexual touching child','touched my daughter','daughter was touched','touched her','touching her','child was touched','molested my child','inappropriate touch child','sexual assault child'],
    'pocso-19':['pocso report','report child sexual offence','police report child offence','reporting','police report','report'],
    'pocso-24':['record child statement','child statement police','pocso statement','statement to police'],
    'pocso-27':['child medical examination','medical exam pocso','medical care child sexual assault','medical care','medical exam'],
}


def extract(file,number,heading):
    text=(DATA/(file+'.txt')).read_text(encoding='utf-8')
    if number=='2-47':
        a=re.search(r'\(47\)\s*"unfair trade practice"',text)
        b=re.search(r'CHAPTER II',text[a.end():]);return text[a.start():a.end()+b.start()].strip()
    if number=='2-1-d':
        a=re.search(r'\(d\)\s*[“"]child[”"]\s*means.*?;',text,re.S);return a.group()
    pattern=r'^\s*'+str(number)+r'\s*\.\s*'+re.escape(heading)
    matches=list(re.finditer(pattern,text,re.M|re.I))
    if not matches:raise ValueError((file,number,heading))
    a=matches[-1]
    b=re.search(r'^\s*'+str(int(number)+1)+r'\s*\.\s*',text[a.end():],re.M)
    if not b:raise ValueError('Missing section boundary '+str(number))
    return text[a.start():a.end()+b.start()].strip()


def main():
    rows=json.loads((DATA/'sources.json').read_text(encoding='utf-8'))
    for row in rows:
        row.setdefault('domains',['theft'] if row['id'].startswith('bns-') else ['consumer','food'])
        row.setdefault('case_stage','initial')
    for spec in SPECS:
        file=spec['file'];number=spec['number'];title,url,version=FILES[file]
        sid={'consumer':'cpa','specific-relief':'sra','food':'fssa'}.get(file,file)+'-'+str(number)
        excerpt=extract(file,number,spec['heading'])
        row={k:spec[k] for k in ('issue','plain_explanation','when_to_use','do_not_use_when','helpful_material','elements')}
        row.update(id=sid,kind='statute',title=title,section='Section '+str(number).replace('-','(')+(')' if isinstance(number,str) and '-' in number else ''),
            text=excerpt,context_text='Source-checked explanatory summary, not a verbatim quotation: '+spec['plain_explanation']+' '+spec['when_to_use']+' '+spec['do_not_use_when'],
            url=url,domains=[spec['domain']],case_stage='follow_up' if sid in FOLLOW_UP_IDS else 'initial',keywords=spec['keywords'] or KEYWORD_OVERRIDES.get(sid,WORDS[spec['domain']]),
            verified_on='2026-11-18',version=version,status='Excerpt checked against the stored official publication; not a comprehensive current-law certification',
            sha256=hashlib.sha256((DATA/(file+'.pdf')).read_bytes()).hexdigest(),examples=[])
        if sid=='pocso-2-1-d':row['section']='Section 2(1)(d)'
        if file=='bns':row['effective_from']='2024-07-01'
        if file=='pocso':row['effective_from']='2012-11-14'
        rows=[r for r in rows if r['id']!=sid];rows.append(row)
    # Extend the existing consumer notes without changing their statutory excerpts.
    consumer_elements={'cpa-2-7':['Purchase or hiring for consideration','Relevant consumer status and exclusions'],
        'cpa-2-10':['Goods and the reported shortcoming','Relevant quality or contractual standard'],
        'cpa-2-11':['Service and required performance','Reported fault, omission or inadequacy'],
        'cpa-35':['Complainant status','Subject of complaint and appropriate filing route'],
        'cpa-39':['Relevant allegation established before the Commission','Suitable remedy and statutory conditions']}
    theft_elements={'bns-303':['Movable property','Possession of another','Movement for the taking','Absence of consent','Dishonest intention'],
        'bns-304':['Theft conditions','Sudden, quick or forcible seizure','From a person or their possession'],
        'bns-305':['Theft conditions','One of the listed settings or property categories'],
        'bns-309':['Theft or extortion','Additional statutory harm, restraint or immediate fear','Connection to the taking or delivery']}
    for row in rows:
        row.setdefault('elements',(consumer_elements|theft_elements).get(row['id'],[]))
        if row['id']=='cpa-69':row['allowed_procedural_periods']=['two years','2 years']
        if row['id']=='sra-6':row['allowed_procedural_periods']=['six months','6 months']
    (DATA/'sources.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Source collection:',len(rows),'provisions')


if __name__=='__main__':main()
