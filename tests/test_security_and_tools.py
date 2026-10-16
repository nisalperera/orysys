import asyncio
from types import SimpleNamespace
import pytest
from pydantic import BaseModel, ConfigDict
from app.security.token_bucket import TokenBucket
from app.tools.registry import Registry, Spec, ToolError

class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int

def user(role):
    return SimpleNamespace(role=SimpleNamespace(value=role))

def test_bucket_refill_and_user_isolation():
    now=[0.0]
    b=TokenBucket(2, 0.5, lambda:now[0])
    assert b.consume('a') == (True,0)
    assert b.consume('a') == (True,0)
    assert b.consume('a') == (False,2)
    assert b.consume('b') == (True,0)
    now[0]=2
    assert b.consume('a') == (True,0)

@pytest.mark.parametrize('capacity,rate',[(0,1),(1,0),(1,-1)])
def test_invalid_bucket(capacity,rate):
    with pytest.raises(ValueError): TokenBucket(capacity,rate)

def test_registry_permissions_validation_and_success():
    calls=[]
    async def handle(u,p): calls.append(1); return p.value*2
    r=Registry({'v':user('viewer'),'a':user('analyst'),'d':user('admin')})
    r.register(Spec('analysis',Args,frozenset({'analyst','admin'}),handle))
    async def check():
        for uid in ['v','unknown']:
            with pytest.raises(ToolError) as exc: await r.execute(uid,'analysis',{'value':1})
            assert exc.value.code=='forbidden'
        with pytest.raises(ToolError) as exc: await r.execute('a','analysis',{'value':1,'role':'admin'})
        assert exc.value.code=='invalid_parameters'
        assert calls==[]
        assert await r.execute('a','analysis',{'value':3})==6
        assert await r.execute('d','analysis',{'value':4})==8
        with pytest.raises(ToolError): await r.execute('d','shell',{})
    asyncio.run(check())

def test_timeouts_errors_events():
    async def slow(u,p): await asyncio.sleep(1)
    async def bad(u,p): raise RuntimeError('private details')
    r=Registry({'a':user('analyst')})
    r.register(Spec('slow',Args,frozenset({'analyst'}),slow,.001))
    r.register(Spec('bad',Args,frozenset({'analyst'}),bad))
    ev=[]
    async def check():
        for name,code in [('slow','timeout'),('bad','unavailable')]:
            with pytest.raises(ToolError) as e: await r.execute('a',name,{'value':1},lambda t,**d:ev.append((t,d)))
            assert e.value.code==code and 'private details' not in str(e.value)
    asyncio.run(check())
    assert any(d.get('status')=='timeout' for t,d in ev)

def test_cancellation_propagates():
    async def cancel(u,p): raise asyncio.CancelledError()
    r=Registry({'a':user('admin')})
    r.register(Spec('cancel',Args,frozenset({'admin'}),cancel))
    async def check():
        with pytest.raises(asyncio.CancelledError): await r.execute('a','cancel',{'value':1})
    asyncio.run(check())
