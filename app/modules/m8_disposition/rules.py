from app.domain import day
def start_point(ctx, event):
    # 停用起点取复检日之前本设备最近一次校准证书的生效日（上次确认合格点），不以复检当天截断。
    candidates=[c for key,c in ctx['certs'].items() if key!=event['cert'] and c['canonical']==event['canonical'] and day(c['valid_from'])<=day(event['checked_at'])]
    if not candidates:return None
    return max(candidates,key=lambda c:(day(c['valid_from']),c['cert']))
def apply(ctx):
    verdicts={v['行号']:v['结论'] for v in ctx['verdicts']}
    events=[];retests={}
    for key in sorted(ctx['certs']):
        cert=ctx['certs'][key]
        if not cert['checked_at']:continue
        row={'设备':cert['canonical'],'复检证书':key,'复检日':cert['checked_at'],'调整前':cert['pre_result'],'调整后':cert['post_result'] or '—','停用起点':'—','起点来源':'—','恢复时点':'—'}
        affected=[]
        if cert.get('conflicted'):row['状态']='定义冲突，待人工界定'
        elif cert['pre_result']=='合格':row['状态']='复检合格，无处置'
        else:
            row['恢复时点']=cert['resumed_at'] if cert['post_result']=='合格' else '未恢复'
            source=start_point(ctx,cert)
            if source is None:row.update(停用起点='无法确定',状态='缺上次校准，待人工界定')
            else:
                row.update(停用起点=source['valid_from'],起点来源=source['cert'],状态='已恢复' if cert['post_result']=='合格' else '停用中')
                begin=day(source['valid_from']);end=day(cert['resumed_at']) if cert['post_result']=='合格' else None
                # 影响区间为半开[停用起点,恢复时点)：调整后恢复时点起的合格测量不作废。
                affected=[m for m in ctx['measurements'] if m['canonical']==cert['canonical'] and begin<=day(m['measured_at']) and (end is None or day(m['measured_at'])<end)]
        row['受影响测量']=len(affected)
        for m in affected:
            item=retests.setdefault(m['行号'],{'设备':m['canonical'],'原证书':m['cert'],'测量日':m['measured_at'],'测量值_V':m['value_v'],'原结论':verdicts[m['行号']],'处置':'需复测','复检证书':[],'行号':m['行号']})
            if key not in item['复检证书']:item['复检证书'].append(key)
        events.append(row)
    events.sort(key=lambda r:(r['设备'],r['复检日'],r['复检证书']))
    items=sorted(({**i,'复检证书':'+'.join(i['复检证书'])} for i in retests.values()),key=lambda r:(r['设备'],r['测量日'],r['行号']))
    ctx['dispositions']=events;ctx['retests']=items
    metrics=[['复检事件',len(events),'起'],['停用设备',len({r['设备'] for r in events if r['调整前']=='超差'}),'台'],['复测项目',len(items),'项'],['未恢复',sum(r['恢复时点']=='未恢复' for r in events),'起']]
    return {'rows':events,'retests':items,'metrics':metrics}
