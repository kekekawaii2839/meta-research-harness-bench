"""Controller-written abstract ABI tests, run only inside the builder container."""
import hashlib
import importlib.util
import unittest

spec=importlib.util.spec_from_file_location('candidate','/inputs/harness.py')
harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)


def action(kind, tool=None, arguments=None):
    return {'kind':kind,'message':'abstract interface fixture','tool_name':tool,'arguments':arguments,
            'status':'completed' if kind=='final' else None,'content':{} if kind=='final' else None,
            'artifacts':[] if kind=='final' else None,'omissions':[] if kind=='final' else None}


class Budget:
    def __init__(self):self.calls=0
    def remaining(self):return {'model_calls':10-self.calls,'tool_calls':20,'wall_seconds':100,'cancelled':False}


class Model:
    def __init__(self,budget,actions):self.budget=budget;self.actions=list(actions);self.images=[]
    def complete(self,request,*,output_schema,image_ids=None):
        self.budget.calls+=1;self.images.append(image_ids)
        return {'response':self.actions.pop(0),'call_id':self.budget.calls,'usage':None}


class Tools:
    def __init__(self):self.calls=[]
    def call(self,name,arguments):
        self.calls.append((name,arguments))
        if name=='artifact.view_image':return {'path':'fixture.png','image_id':'image-fixture','sha256':'0'*64}
        if name=='artifact.write_text':return {'path':arguments['path'],'sha256':hashlib.sha256(arguments['text'].encode()).hexdigest()}
        if name=='artifact.read_text':return {'path':arguments['path'],'text':'fixture','sha256':hashlib.sha256(b'fixture').hexdigest()}
        if name=='cpu.run':return {'returncode':0,'stdout':'fixture','stderr':'','timed_out':False,'output_limited':False}
        return {'text':'fixture','sha256':'0'*64}


class ABITests(unittest.TestCase):
    def execute(self,group,name,args,kind='EXP'):
        budget=Budget();tools=Tools();model=Model(budget,[action('tool',name,args),action('final')])
        view={'task_type':kind,'tools':[group],'asset_manifest':[],'output_contract':{}}
        result=harness.run(view,model,tools,budget)
        self.assertEqual([x[0] for x in tools.calls],[name])
        self.assertEqual(result['status'],'completed')
        return model,result
    def test_artifact_group_write(self):self.execute('artifact_read_write','artifact.write_text',{'path':'x.txt','text':'fixture'})
    def test_artifact_group_read(self):self.execute('artifact_read_write','artifact.read_text',{'path':'x.txt'})
    def test_cpu_group(self):self.execute('cpu_python_execution','cpu.run',{'script':'x.py'})
    def test_image_group_and_pixels_request(self):
        model,_=self.execute('artifact_image_view','artifact.view_image',{'path':'fixture.png'},'WRITE_EVIDENCE')
        self.assertEqual(model.images[1],['image-fixture'])
    def test_literature_exact_capability(self):self.execute('literature.search','literature.search',{'query':'abstract fixture'},'LIT')
    def test_all_routes_independent(self):
        for kind in ('LIT','IDEA','EXP','WRITE_CONTENT','WRITE_EVIDENCE'):
            budget=Budget();model=Model(budget,[action('final')]);tools=Tools()
            self.assertEqual(harness.run({'task_type':kind,'tools':[],'output_contract':{}},model,tools,budget)['status'],'completed')


if __name__=='__main__':unittest.main(verbosity=2)
