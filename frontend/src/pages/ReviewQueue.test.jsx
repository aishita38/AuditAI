// @vitest-environment jsdom
import React from 'react';
import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import ReviewQueue from './ReviewQueue';
import CaseDetail from './CaseDetail';
import CaseEvidence from '../components/CaseEvidence';
import {RecordLinksProvider} from '../components/RecordLink';
import {reviewQueueApi,recordsApi} from '../api/client';
vi.mock('../api/client',()=>({reviewQueueApi:{sync:vi.fn(),list:vi.fn(),detail:vi.fn(),decide:vi.fn(),comment:vi.fn()},recordsApi:{lookup:vi.fn()}}));
const item={id:101,case_type:'circular_payment',severity:'high',reason:'3-transfer loop',status:'open',created_at:'2026-10-18T10:00:00Z',maker_id:null,checker_id:null,evidence:{accounts:['A','B','A'],transfers:[{transaction_id:'T1',sender_account:'A',receiver_account:'B',amount:'100',currency:'INR'}]},related_records:[],permissions:{can_make:true,can_check:false},audit_trail:[{id:1,action:'created',actor:'admin',timestamp:'2026-10-18T10:00:00Z',notes:'Snapshot saved'}]};
function app(){return render(<MemoryRouter initialEntries={['/review-queue?case_type=circular_payment&status=open&severity=high']}><Routes><Route path="/review-queue" element={<ReviewQueue/>}/><Route path="/review/cases/:caseId" element={<CaseDetail/>}/></Routes></MemoryRouter>);}
beforeEach(()=>{vi.resetAllMocks();reviewQueueApi.sync.mockResolvedValue({});reviewQueueApi.list.mockResolvedValue({data:{items:[item],total:1}});reviewQueueApi.detail.mockResolvedValue({data:item});recordsApi.lookup.mockImplementation(async records=>({data:records.map(r=>({...r,exists:r.id!=='MISSING'}))}));});
afterEach(cleanup);
describe('unified review navigation',()=>{
 it('opens a case from a queue row and restores filters with the back link',async()=>{
  const user=userEvent.setup();app();
  await user.click(await screen.findByRole('link',{name:'Open case #101'}));
  expect(await screen.findByRole('heading',{name:'Case #101'})).toBeTruthy();
  expect(screen.getByRole('heading',{name:'Circular payment evidence'})).toBeTruthy();
  expect(await screen.findByRole('link',{name:'T1'})).toBeTruthy();
  expect(screen.getByText('Snapshot saved')).toBeTruthy();
  expect(screen.getByRole('button',{name:'Submit maker recommendation'})).toBeTruthy();
  await user.click(screen.getByRole('link',{name:/Back to review queue/}));
  expect(await screen.findByRole('heading',{name:'Shared review queue'})).toBeTruthy();
  expect(screen.getByLabelText('Case type').value).toBe('circular_payment');
  expect(screen.getByLabelText('Status').value).toBe('open');expect(screen.getByLabelText('Severity').value).toBe('high');
 });
 it('opens the real case-number link with keyboard navigation',async()=>{
  const user=userEvent.setup();app();const link=await screen.findByRole('link',{name:'#101'});expect(link.getAttribute('href')).toContain('/review/cases/101');link.focus();await user.keyboard('{Enter}');expect(await screen.findByRole('heading',{name:'Case #101'})).toBeTruthy();
 });
 it('does not offer checker actions when permissions block the same maker',async()=>{
  reviewQueueApi.detail.mockResolvedValue({data:{...item,permissions:{can_make:false,can_check:false,maker_reason:'Recommendation already recorded.',checker_reason:'Checker must be different from maker.'}}});app();await userEvent.click(await screen.findByRole('link',{name:'#101'}));expect(await screen.findByText(/Checker must be different from maker/)).toBeTruthy();expect(screen.queryByRole('button',{name:'Submit checker sign-off'})).toBeNull();
 });
 it('reports a missing case instead of an empty page',async()=>{
  reviewQueueApi.detail.mockRejectedValue({response:{status:404}});app();await userEvent.click(await screen.findByRole('link',{name:'#101'}));expect(await screen.findByRole('alert')).toHaveProperty('textContent','Case not found.');
 });
});
it('keeps all snapshot transfers, expands long lists, and marks deleted records',async()=>{
 const rows=Array.from({length:12},(_,i)=>({transaction_id:i===0?'MISSING':`T${i}`,amount:100,sender_account:'A',receiver_account:'B'}));
 render(<MemoryRouter><RecordLinksProvider records={rows.map(r=>({kind:'transfer',id:r.transaction_id}))}><CaseEvidence item={{...item,evidence:{transfers:rows}}}/></RecordLinksProvider></MemoryRouter>);
 expect(await screen.findByText('MISSING · Not found')).toBeTruthy();
 const control=screen.getByText('Show all 12 records (2 more)');await userEvent.click(control);expect(control.parentElement.open).toBe(true);expect(await screen.findByRole('link',{name:'T11'})).toBeTruthy();expect(screen.getAllByText('amount · Rule trigger').length).toBe(12);
});
it('renders generic vendor evidence with every vendor and highlights shared bank fields',async()=>{
 const vendors=[{vendor_id:'V1',bank_account:'BANK'},{vendor_id:'V2',bank_account:'BANK'}];
 render(<MemoryRouter><RecordLinksProvider records={vendors.map(v=>({kind:'vendor',id:v.vendor_id}))}><CaseEvidence item={{case_type:'vendor_check',evidence:{vendors,explanation:'Shared bank'}}}/></RecordLinksProvider></MemoryRouter>);
 expect(await screen.findByRole('link',{name:'V2'})).toBeTruthy();expect(screen.getAllByText('bank account · Rule trigger').length).toBe(2);expect(screen.getByText('Shared bank')).toBeTruthy();
});

 it('shows a missing claim without creating a broken claim link',async()=>{
  const evidence={claim:{claim_id:'MISSING',claimed_amount:4500},payments:[{transaction_id:'PAY1',claim_id:'MISSING',amount:45000}],prediction:null};
  render(<MemoryRouter><RecordLinksProvider records={[{kind:'claim',id:'MISSING'},{kind:'transfer',id:'PAY1'}]}><CaseEvidence item={{case_type:'expense_claim',evidence}}/></RecordLinksProvider></MemoryRouter>);
  expect(await screen.findByText('MISSING · Claim not found')).toBeTruthy();expect(screen.queryByRole('link',{name:'MISSING'})).toBeNull();expect(await screen.findByRole('link',{name:'PAY1'})).toBeTruthy();
 });
 it('renders claim plus all reconciliation payments and payroll payment plus roster snapshots',async()=>{
  const {unmount}=render(<MemoryRouter><RecordLinksProvider records={[{kind:'claim',id:'C1'},{kind:'transfer',id:'P1'},{kind:'transfer',id:'P2'}]}><CaseEvidence item={{case_type:'reconciliation',evidence:{claim_id:'C1',claim_amount:4500,payments:[{transaction_id:'P1',amount:45000},{transaction_id:'P2',amount:45000}],flags:['payment_total_mismatch']}}}/></RecordLinksProvider></MemoryRouter>);
  expect(await screen.findByRole('link',{name:'C1'})).toBeTruthy();expect(await screen.findByRole('link',{name:'P2'})).toBeTruthy();expect(screen.getAllByText('amount · Rule trigger').length).toBe(2);unmount();
  render(<MemoryRouter><RecordLinksProvider records={[{kind:'payroll_payment',id:'PAY'},{kind:'employee',id:'EMP'}]}><CaseEvidence item={{case_type:'payroll_check',evidence:{payment:{payment_id:'PAY',bank_account:'BANK'},employee:{employee_id:'EMP',bank_account:'BANK'}}}}/></RecordLinksProvider></MemoryRouter>);
  expect(await screen.findByRole('link',{name:'PAY'})).toBeTruthy();expect(await screen.findByRole('link',{name:'EMP'})).toBeTruthy();
 });
