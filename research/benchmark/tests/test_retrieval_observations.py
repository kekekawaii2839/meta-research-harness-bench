import copy
import unittest
from mrhbench.io import ProtocolError, digest
from mrhbench.retrieval_observations import extract_retrieval_observations


def rpc(name, value, args=None, sequence=1, ok=True):
    return {'request':{'operation':'tool','sequence':sequence,'arguments':{'name':name,'arguments':args or {}}},
            'response':{'ok':ok,'sequence':sequence,'value':value}}


class RetrievalObservationTests(unittest.TestCase):
    def setUp(self):
        self.docs=[{'document_id':'d','version':'v1','pdf_sha256':'a'*64}]
        self.sub={'content':{'claim_document_version_location_map':[
            {'document_id':'d','version':'v1','claim':'test claim','location':'p2'}]}}
    def run_rows(self, rows, sub=None):
        return extract_retrieval_observations(rows=rows,submission=self.sub if sub is None else sub,documents=self.docs)
    def test_distinct_stages_and_duplicate_claims(self):
        hit={'document_id':'d','version':'v1'}
        self.sub['content']['claim_document_version_location_map']*=2
        rows=[rpc('literature.search',[hit,hit]),rpc('literature.read',{**hit,'text':'abstract'},{'document_id':'d'},2),
              rpc('literature.read_page',{**hit,'text':'page','page_number':2,'page_text_hash':digest('page')},
                  {'document_id':'d','page_number':2},3)]
        result=self.run_rows(rows)
        self.assertEqual(result['counts'],dict(returned=1,abstract_read=1,page_read=1,adopted=1))
        self.assertEqual(len(result['events']),6)
        self.assertFalse(result['invalid'])
    def test_failure_not_read(self):
        result=self.run_rows([rpc('literature.read',{'document_id':'d','version':'v1','text':'x'},{'document_id':'d'},ok=False)])
        self.assertEqual(result['counts']['abstract_read'],0)
        self.assertEqual(len(result['failed_calls']),1)
    def test_page_unique_version_binding_only(self):
        page={'document_id':'d','text':'x','page_number':2}
        row=rpc('literature.read_page',page,{'document_id':'d','page_number':2})
        result=self.run_rows([row]);self.assertEqual(result['events'][0]['version_source'],'fixed_corpus_unique_version')
        self.docs.append({'document_id':'d','version':'v2'})
        self.assertEqual(self.run_rows([row])['invalid'][0]['reason'],'ambiguous_missing_page_version')
    def test_no_missing_abstract_or_adopted_version_inference(self):
        del self.sub['content']['claim_document_version_location_map'][0]['version']
        result=self.run_rows([rpc('literature.read',{'document_id':'d','text':'x'},{'document_id':'d'})])
        self.assertEqual(len(result['invalid']),2)
    def test_unknown_or_wrong_version(self):
        result=self.run_rows([rpc('literature.search',[{'document_id':'missing','version':'v1'},{'document_id':'d','version':'v2'}])])
        self.assertEqual(result['counts']['returned'],0);self.assertEqual(len(result['invalid']),2)
    def test_request_response_mismatch(self):
        row=rpc('literature.read',{'document_id':'d','version':'v1','text':'x'},{'document_id':'other'})
        self.assertEqual(self.run_rows([row])['invalid'][0]['reason'],'request_response_document_mismatch')
        row['response']['sequence']=2
        self.assertEqual(self.run_rows([row])['invalid'][0]['reason'],'response_sequence_mismatch')
    def test_explicit_page_version_and_hash_mismatch(self):
        page={'document_id':'d','version':'v2','text':'x','page_number':1}
        row=rpc('literature.read_page',page,{'document_id':'d','page_number':1})
        self.assertEqual(self.run_rows([row])['counts']['page_read'],0)
        page['version']='v1';page['source_sha256']='b'*64
        self.assertEqual(self.run_rows([row])['invalid'][0]['reason'],'page_source_hash_mismatch')
    def test_no_free_text_adoption(self):
        result=self.run_rows([],{'content':{'summary':'adopt doc d v1 p2','references':[{'document_id':'d','version':'v1'}]}})
        self.assertEqual(result['counts']['adopted'],0)
    def test_duplicate_receipt_not_extra_event(self):
        row=rpc('literature.search',[{'document_id':'d','version':'v1'}])
        result=self.run_rows([row,copy.deepcopy(row)])
        self.assertEqual(len([e for e in result['events'] if e['stage']=='returned']),1)
        self.assertEqual(result['invalid'][0]['reason'],'invalid_or_duplicate_sequence')
    def test_reject_duplicate_corpus_identity(self):
        self.docs*=2
        with self.assertRaises(ProtocolError):self.run_rows([])


if __name__=='__main__':unittest.main()
