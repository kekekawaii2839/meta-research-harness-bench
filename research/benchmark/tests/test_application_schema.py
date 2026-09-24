import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from mrhbench.providers import validate_application_schema,WIRE_SCHEMA
from mrhbench.io import ProtocolError
from jsonschema import ValidationError

class ApplicationSchemaTests(unittest.TestCase):
    def test_dynamic_arguments(self):
        s={'type':'object','properties':{'arguments':{'type':['object','null']}},'required':['arguments']}
        validate_application_schema(s,{'arguments':{'path':'x.py','text':'print(1)'}},check_response=True)
        with self.assertRaises(ValidationError):validate_application_schema(s,{'arguments':3},check_response=True)
    def test_remote_resolution_denied(self):
        with self.assertRaises(ProtocolError):validate_application_schema({'anyOf':[{'$ref':'file:///private.json'}]})
    def test_wire_exact(self):
        validate_application_schema(WIRE_SCHEMA,{'payload_json':'{}'},check_response=True)
        with self.assertRaises(ValidationError):validate_application_schema(WIRE_SCHEMA,{'payload_json':{},'role':'judge'},check_response=True)

if __name__=='__main__':unittest.main()
