"""Missing corroboration must not suppress potentially relevant legal provisions."""
import copy
import unittest
from unittest.mock import patch
import core


class IssueSpottingTests(unittest.TestCase):
    def case(self,story='On 10 November 2026 someone stole my phone from my bedroom. I have no CCTV or witnesses.'):
        return core.offline_intake(story,'')

    def test_theft_description_retrieves_official_provisions_without_evidence(self):
        self.assertEqual({s['id'] for s in core.retrieve(self.case())}, {'bns-303','bns-304','bns-305','bns-309'})

    def test_no_evidence_still_produces_useful_source_guidance_offline(self):
        with patch('core.configured',return_value=False):
            answer,_=core.analyse(self.case())
        law=next(l for l in answer['laws'] if l['source_id']=='bns-303')
        self.assertIn('without consent',law['explanation'])
        self.assertIn('starting point',law['when_to_use'])
        self.assertIn('when and where',law['missing'])

    def test_pre_commencement_dates_do_not_recommend_bns(self):
        case=self.case('On 10 November 2022 someone stole my phone.')
        self.assertFalse(any(s['id'].startswith('bns-') for s in core.retrieve(case)))

    def test_undated_theft_keeps_conditional_references(self):
        self.assertIn('bns-303',[s['id'] for s in core.retrieve(self.case('Someone stole my phone.'))])

    def test_model_questions_do_not_manufacture_theft_relevance(self):
        case=self.case('My neighbour blocks sunlight.')
        case['questions']=['Was the phone stolen? Was there robbery?']
        self.assertEqual(core.retrieve(case),[])

    def test_live_supported_means_matches_description_not_proven_crime(self):
        case=self.case();source=next(s for s in core.sources() if s['id']=='bns-303')
        candidate={'overview':'Your account raises a possible theft issue even without CCTV.',
            'laws':[{'source_id':'bns-303','support':'supported','issue':'Possible taking without consent',
                     'when_to_use':source['when_to_use'],'explanation':'This provision may fit the reported taking.',
                     'connection':'You report a phone being taken from your possession.',
                     'missing':'Clarify when it was last seen and whether permission was given.',
                     'objection':'If it was misplaced or taken with consent, the theft conditions may not be met.'}],
            'scenarios':[],'next_steps':['Write down what you remember.'],'limits':['This does not establish guilt.']}
        with patch('core.configured',return_value=True),patch('core.model_json',return_value=candidate):
            answer,_=core.analyse(case)
        self.assertEqual(answer['laws'][0]['relevance'],'Matches the reported description')
        self.assertIn('not been independently verified',answer['laws'][0]['evidence_status'])
        self.assertTrue(any('1 July 2024' in s for s in answer['limits']))

    def test_snatching_and_robbery_guides_keep_distinct_conditions(self):
        sources={s['id']:s for s in core.sources()}
        self.assertIn('sudden',sources['bns-304']['when_to_use'])
        self.assertIn('immediate fear',sources['bns-309']['when_to_use'])
        self.assertIn('does not establish robbery',sources['bns-309']['when_to_use'])

    def test_source_notes_preserve_custody_property_branch(self):
        source=next(s for s in core.sources() if s['id']=='bns-305')
        candidate={'overview':'Possible theft issue.','laws':[{'source_id':'bns-305','support':'conditional',
            'explanation':'Unreliable generated definition','connection':'You report a taking from a room.',
            'missing':'CCTV is mandatory.','objection':'An office can never qualify.'}],
            'scenarios':[],'next_steps':[],'limits':[]}
        result=core.validate_analysis(candidate,[source])
        law=result['laws'][0]
        self.assertIn('commercial office may still',law['objection'])
        self.assertNotIn('mandatory',law['missing'])
        self.assertIn('custody of property',law['explanation'])

    def test_property_practice_does_not_invent_burden_of_proof(self):
        source=next(s for s in core.sources() if s['id']=='bns-303')
        candidate={'overview':'Possible theft issue.','laws':[{'source_id':'bns-303','support':'supported',
            'explanation':'Possible provision','connection':'Reported taking.','missing':'Clarify consent.','objection':'Consent may be disputed.'}],
            'scenarios':[{'question':'What if consent is disputed?','effect':'The accused must prove it.','preparation':'Invent a document.'}],
            'next_steps':['You must have CCTV.'],'limits':[]}
        result=core.validate_analysis(candidate,[source])
        text=str(result)
        self.assertNotIn('accused must prove',text)
        self.assertNotIn('must have CCTV',text)
        self.assertNotIn('Invent a document',text)

    def test_food_safety_starters_do_not_depend_on_uploaded_proof(self):
        case=self.case('A restaurant sold contaminated food and I became sick.')
        ids={s['id'] for s in core.retrieve(case)}
        self.assertTrue({'fssa-26','fssa-59'}<=ids)
        self.assertIn('fssa-65',ids)  # later only if injury and causal link are assessed

    def test_consumer_refund_does_not_surface_unfair_trade_practice_automatically(self):
        ids={s['id'] for s in core.retrieve(self.case('I bought a phone and the seller refuses to refund me.'))}
        self.assertTrue({'cpa-2-7','cpa-35','cpa-39'}<=ids)
        self.assertNotIn('cpa-2-47',ids)

    def test_property_dispossession_retrieves_civil_remedy_starters(self):
        ids={s['id'] for s in core.retrieve(self.case('My brother forcibly removed me from our inherited house.'))}
        self.assertTrue({'sra-5','sra-6','sra-34','sra-38'}<=ids)

    def test_rape_description_does_not_equate_distinct_sexual_offences(self):
        ids={s['id'] for s in core.retrieve(self.case('An adult raped me. I have no witness.'))}
        self.assertTrue({'bns-63','bns-64'}<=ids)
        self.assertFalse({'bns-74','bns-75'}&ids)
        self.assertFalse(any(sid.startswith('pocso-') for sid in ids))

    def test_child_case_surfaces_child_protection_only_with_child_and_sexual_facts(self):
        story='My 15 year old daughter says an adult touched her.'
        ids={s['id'] for s in core.retrieve(self.case(story))}
        self.assertIn('pocso-2-1-d',ids)
        self.assertIn('pocso-7',ids)
        unrelated={s['id'] for s in core.retrieve(self.case('My daughter and I inherited a house.'))}
        self.assertFalse(any(sid.startswith('pocso-') for sid in unrelated))

    def test_cross_subject_retrieval_keeps_more_than_eight_sources(self):
        story='My 15 year old daughter was raped; the family is asking how to report and get medical care.'
        ids={s['id'] for s in core.retrieve(self.case(story))}
        self.assertIn('bns-63',ids)
        self.assertIn('pocso-3',ids)
        self.assertIn('pocso-19',ids)
        self.assertIn('pocso-27',ids)
        self.assertLessEqual(len(ids),12)


if __name__=='__main__':unittest.main()
