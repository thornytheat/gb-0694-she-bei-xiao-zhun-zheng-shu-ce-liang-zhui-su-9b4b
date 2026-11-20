from app.pipeline import calculate
HEADER='cert,device,alias,parent,valid_from,valid_to,minimum,maximum,unit,revoked,measured_at,value,measure_unit,version,checked_at,pre_result,post_result,resumed_at'
ROOT=('ROOT','REF-001','','','2025-01-01','2028-01-01','0','1000','V','no','2026-01-05','100','V','1','','','','')
def csv_of(*rows):return HEADER+'\n'+'\n'.join(','.join(r) for r in (ROOT,)+rows)+'\n'
def meas(cert,device,day_,vf='2026-01-01',vt='2026-11-15',value='5'):
    return (cert,device,'', 'ROOT',vf,vt,'0','10','V','no',day_,value,'V','1','','','','')
def recheck(cert,device,checked,pre,post,resumed,vf,mday=None,vt='2027-11-15'):
    return (cert,device,'','ROOT',vf,vt,'0','10','V','no',mday or resumed or checked,'5','V','1',checked,pre,post,resumed)
def test_sample_event_window(ctx):
    row=ctx['stages']['8']['rows'][0]
    assert (row['设备'],row['停用起点'],row['起点来源'],row['恢复时点'],row['受影响测量'],row['状态'])==('D0041','2026-01-01','C0041','2026-11-15',2,'已恢复')
def test_sample_retests_before_check_day(ctx): # TRAP-26 复检当天截断会漏掉调整前流出的测量
    dates={r['测量日'] for r in ctx['retests']}
    assert dates=={'2026-03-10','2026-06-10'} and all(d<'2026-11-10' for d in dates)
def test_sample_post_recovery_kept(ctx): # TRAP-27 回退到上次校准会把调整后的合格结果作废
    assert '2026-11-18' not in {r['测量日'] for r in ctx['retests']}
    assert next(v for v in ctx['verdicts'] if v['证书']=='C0042')['结论']=='可采用'
def test_retest_fields(ctx):
    item=next(r for r in ctx['retests'] if r['测量日']=='2026-03-10')
    assert (item['原证书'],item['原结论'],item['处置'],item['复检证书'])==('C0041','可采用','需复测','C0042')
def test_verdict_stage_untouched(ctx): # M8不重写M6结论，处置单列
    assert all(v['结论']=='可采用' for v in ctx['verdicts'] if v['证书']=='C0041')
def test_window_half_open():
    csv=csv_of(meas('OLD1','D1','2026-01-01'),recheck('R1','D1','2026-11-10','超差','合格','2026-11-15','2026-11-15',mday='2026-11-15'))
    dates={r['测量日'] for r in calculate(csv)['retests']}
    assert '2026-01-01' in dates and '2026-11-15' not in dates
def test_unrecovered_open_window():
    csv=csv_of(meas('OLD1','D1','2026-05-05',vt='2026-11-12'),meas('OLD1','D1','2026-11-11',vt='2026-11-12'),recheck('R1','D1','2026-11-10','超差','不合格','','2026-11-12',mday='2026-11-12'))
    stage=calculate(csv)['stages']['8'];row=stage['rows'][0]
    assert (row['恢复时点'],row['状态'])==('未恢复','停用中')
    assert {'2026-05-05','2026-11-11'}<={r['测量日'] for r in stage['retests']}
def test_unknown_start_point():
    csv=csv_of(recheck('R1','D1','2026-11-10','超差','合格','2026-11-15','2026-11-15'))
    row=calculate(csv)['stages']['8']['rows'][0]
    assert (row['停用起点'],row['状态'],row['受影响测量'])==('无法确定','缺上次校准，待人工界定',0)
def test_recheck_pass_no_disposition():
    csv=csv_of(meas('OLD1','D1','2026-05-05'),recheck('R1','D1','2026-11-10','合格','','','2026-11-15',mday='2026-11-16'))
    stage=calculate(csv)['stages']['8']
    assert stage['rows'][0]['状态']=='复检合格，无处置' and stage['retests']==[]
def test_overlapping_events_dedup(): # TRAP-28 同一测量被多个事件覆盖只生成一项复测
    csv=csv_of(meas('OLD1','D1','2026-05-05',vt='2026-06-20'),
        recheck('R1','D1','2026-06-01','超差','合格','2026-06-20','2026-06-20',mday='2026-06-21',vt='2027-06-20'),
        recheck('R2','D1','2026-06-10','超差','合格','2026-07-01','2026-07-01',mday='2026-07-02',vt='2027-07-01'))
    stage=calculate(csv)['stages']['8']
    hit=[r for r in stage['retests'] if r['测量日']=='2026-05-05']
    assert len(hit)==1 and hit[0]['复检证书']=='R1+R2'
def test_late_certificate_invalidates_and_recomputes(client): # TRAP-29 证书晚到触发重算
    before=csv_of(meas('OLD1','D1','2026-05-05'))
    after=csv_of(meas('OLD1','D1','2026-05-05'),recheck('R1','D1','2026-11-10','超差','合格','2026-11-15','2026-11-15',mday='2026-11-16'))
    first=client.post('/api/run',json={'csv':before}).get_json();second=client.post('/api/run',json={'csv':after}).get_json()
    assert first['manifest']['run_id']!=second['manifest']['run_id']
    assert first['stages']['8']['rows']==[] and len(second['stages']['8']['retests'])==1
    assert second['stages']['8']['retests'][0]['原结论']=='可采用'
def test_rerun_never_duplicates_retests(client,raw):
    first=client.post('/api/run',json={'csv':raw}).get_json();again=client.post('/api/run',json={'csv':raw}).get_json()
    assert again['reused'] is True and first['manifest']['run_id']==again['manifest']['run_id']
    assert len(client.get('/api/history').get_json())==1
    assert len(again['stages']['8']['retests'])==len(first['stages']['8']['retests'])==2
def test_recheck_field_validation():
    bad=[recheck('R1','D1','2026-11-10','漂移','合格','2026-11-15','2026-11-15'),
         recheck('R1','D1','2026-11-10','超差','合格','','2026-11-15'),
         recheck('R1','D1','2026-11-10','超差','合格','2026-11-09','2026-11-09'),
         recheck('R1','D1','2026-11-10','合格','合格','2026-11-15','2026-11-15'),
         recheck('R1','D1','','超差','合格','2026-11-15','2026-11-15')]
    for row in bad:
        assert any(q['原因码']=='RECHECK' for q in calculate(csv_of(meas('O1','D1','2026-05-05'),row))['quarantine'])
def test_recheck_bad_date_isolated():
    csv=csv_of(meas('O1','D1','2026-05-05'),recheck('R1','D1','2026-13-01','超差','合格','2026-11-15','2026-11-15'))
    assert any(q['原因码']=='DATE' for q in calculate(csv)['quarantine'])
def test_conflicted_recheck_cert_not_disposed():
    first=recheck('R1','D1','2026-11-10','超差','合格','2026-11-15','2026-11-15')
    other=tuple(first[:17]+('2026-11-16',))
    result=calculate(csv_of(meas('O1','D1','2026-05-05'),first,other))
    assert any(q['原因码']=='CONFLICT' for q in result['quarantine'])
    row=result['stages']['8']['rows'][0]
    assert row['状态']=='定义冲突，待人工界定' and result['stages']['8']['retests']==[]
def test_evidence_includes_retests(client,raw):
    run=client.post('/api/run',json={'csv':raw}).get_json()
    text=client.get('/api/evidence.csv?run_id='+run['manifest']['run_id']).data.decode('utf-8-sig')
    assert '8·复测' in text and '需复测' in text
def test_page_shows_window(client,raw):
    client.post('/api/run',json={'csv':raw})
    page=client.get('/work/8').data.decode()
    assert '停用起点' in page and '2026-01-01' in page and '恢复时点' in page and '复测项目' in page
