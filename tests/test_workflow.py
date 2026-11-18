import copy
import io
import json
from pathlib import Path
import unittest
import zipfile
import core


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case=core.intake(core.DEMO_STORY,demo=True)

    def test_sample_is_sorted(self):
        self.assertEqual([e['date'] for e in self.case['events']],['2026-10-05','2026-10-08','2026-10-10','2026-10-20'])

    def test_unknown_dates_not_invented(self):
        c=core.offline_intake('Yesterday I paid. On 3 March 2025 I complained. On 1 March 2025 I ordered.','Receipt reported')
        self.assertEqual([e['date'] for e in c['events']],['2025-03-01','2025-03-03',None])
        self.assertIn('Yesterday',c['events'][-1]['description'])

    def test_invalid_dates_rejected(self):
        self.case['events'][0]['date']='2026-02-30'
        with self.assertRaises(ValueError):core.validate_record(self.case)

    def test_evidence_not_promoted_to_proof(self):
        self.assertTrue(all('not inspected' in e for e in self.case['evidence']))
        self.assertTrue(all('not uploaded or verified' in e['basis'] for e in self.case['events']))

    def test_sample_cannot_answer_arbitrary_story(self):
        with self.assertRaises(ValueError):core.intake('My salary stopped.',demo=True)

    def test_unavailable_source_blocked(self):
        a,s=core.analyse(self.case,True)
        a['laws'][0]['source_id']='imaginary-section'
        with self.assertRaises(ValueError):core.validate_analysis(a,s)

    def test_duplicate_source_blocked(self):
        a,s=core.analyse(self.case,True)
        a['laws'].append(copy.deepcopy(a['laws'][0]))
        with self.assertRaises(ValueError):core.validate_analysis(a,s)

    def test_probability_label_blocked(self):
        a,s=core.analyse(self.case,True)
        a['laws'][0]['support']='95% chance'
        with self.assertRaises(ValueError):core.validate_analysis(a,s)

    def test_unknown_area_has_no_matching_law(self):
        c=core.offline_intake('My neighbour blocks sunlight.','')
        self.assertEqual(core.retrieve(c),[])

    def test_source_text_is_stored_not_generated(self):
        pdfs={'https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf':'consumer.pdf',
              'https://www.mha.gov.in/files/documents/250883_english01042024.pdf':'bns.pdf',
              'https://www.fssai.gov.in/upload/uploadfiles/files/FOOD-ACT.pdf':'food.pdf',
              'https://www.indiacode.nic.in/bitstream/123456789/1583/7/A1963-47.pdf':'specific-relief.pdf',
              'https://www.indiacode.nic.in/bitstream/123456789/2079/1/AA2012-32.pdf':'pocso.pdf',
              'https://www.ncrb.mha.gov.in/uploads/SankalanPortal/ChaptersBNSS.html#173':'bnss-official.html',
              'https://www.ncrb.mha.gov.in/uploads/SankalanPortal/ChaptersBSA.html#63':'bsa-official.html'}
        import hashlib
        for s in core.sources():
            self.assertIn(s['url'],pdfs)
            self.assertTrue(s['text'])
            self.assertEqual(len(s['sha256']),64)
            self.assertEqual(s['sha256'],hashlib.sha256((core.ROOT/'data'/pdfs[s['url']]).read_bytes()).hexdigest())

    def test_formal_draft_keeps_placeholders(self):
        a,_=core.analyse(self.case,True)
        text=core.draft(self.case,a,{})
        self.assertIn('[SENDER NAME AND ADDRESS]',text)
        self.assertIn('[RECIPIENT NAME AND ADDRESS]',text)
        self.assertIn('DRAFT FOR REVIEW',text)
        self.assertNotIn('15 days',text)

    def test_docx_valid_xml_and_escaping(self):
        import xml.etree.ElementTree as ET
        raw=core.docx_bytes('A & B <test>\n\nSecond paragraph')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml=z.read('word/document.xml')
            ET.fromstring(xml)
            self.assertIn(b'A &amp; B &lt;test&gt;',xml)
            self.assertIn(b'Times New Roman',xml)

    def test_draft_formats_keep_route_specific_sections(self):
        examples = {
            'Legal notice': ('GENERAL LEGAL NOTICE', {'response': 'A date to be discussed.'}),
            'Payment demand notice': ('Amount due and calculation', {'amount': 'INR 100 after credits.'}),
            'Reply to notice': ('Paragraph-wise reply', {'reply': 'Paragraph 1 is disputed.'}),
            'Consumer commission complaint': ('Opposite party or parties', {'forum': 'Example Commission'}),
            'Written police complaint': ('The Officer-in-Charge', {'incident': 'Near the gate at 8 pm.'}),
            'Food safety grievance': ('Food item, batch or lot', {'product': 'Product A, lot 23.'}),
            'Civil plaint for advocate review': ('Suit valuation and court fee', {'valuation': 'For review.'}),
            'Case brief': ('CONFIDENTIAL CASE BRIEF FOR LEGAL REVIEW', {'issues': 'Ask about the next hearing.'}),
        }
        for kind, (marker, data) in examples.items():
            with self.subTest(kind=kind):
                text = core.draft(self.case, {}, {'kind': kind, 'facts': 'First fact\nSecond fact', **data})
                self.assertIn(marker, text)
                self.assertIn('1. First fact\n\n2. Second fact', text)
                self.assertTrue(all(value in text for value in data.values()))
                self.assertEqual('VERIFICATION' in text, kind in ('Consumer commission complaint', 'Civil plaint for advocate review'))
                with zipfile.ZipFile(io.BytesIO(core.docx_bytes(text))) as document:
                    xml = document.read('word/document.xml')
                    self.assertIn(b'<w:br/>', xml)
                    self.assertIn(b'w:w="11906" w:h="16838"', xml)

    def test_template_replaces_split_marker_and_preserves_style(self):
        raw=core.docx_bytes('{{CASE_DRAFT}}','Arial',14)
        out=core.docx_bytes('A confirmed event\n\nAnother event',template=raw)
        with zipfile.ZipFile(io.BytesIO(out)) as z:
            xml=z.read('word/document.xml')
            self.assertNotIn(b'{{CASE_DRAFT}}',xml)
            self.assertIn(b'Arial',xml)
            self.assertIn(b'A confirmed event',xml)

    def test_bad_template_rejected(self):
        with self.assertRaises(ValueError):core.docx_bytes('text',template=core.docx_bytes('No marker'))

    def test_template_with_external_link_requires_static_copy(self):
        raw = core.docx_bytes('{{CASE_DRAFT}}')
        external = b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="link" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.com/" TargetMode="External"/></Relationships>'
        edited = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(edited, 'w') as target:
            for name in source.namelist():
                target.writestr(name, source.read(name))
            target.writestr('word/_rels/document.xml.rels', external)
        with self.assertRaisesRegex(ValueError, 'external links'):
            core.docx_bytes('Draft', template=edited.getvalue())


if __name__=='__main__':unittest.main()
