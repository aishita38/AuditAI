// @vitest-environment jsdom
import React from 'react';
import {beforeEach,afterEach,it,expect,vi} from 'vitest';
import {render,screen,cleanup,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MemoryRouter} from 'react-router-dom';
import MasterChecks from './MasterChecks';
import MasterDataImport from '../components/MasterDataImport';
import {masterDataApi,recordsApi,claimsApi,transfersApi} from '../api/client';
vi.mock('../api/client',()=>({masterDataApi:{status:vi.fn(),upload:vi.fn(),findings:vi.fn(),run:vi.fn(),send:vi.fn()},recordsApi:{lookup:vi.fn()},claimsApi:{upload:vi.fn(),uploadReceipt:vi.fn()},transfersApi:{upload:vi.fn()}}));
vi.mock('../auth/AuthContext',()=>({useAuth:()=>({user:{roles:['admin']}})}));
const finding={id:'F1',rule_id:'VENDOR_SHARED_BANK',severity:'high',explanation:'Two vendors share a bank account.',evidence:{vendors:[{vendor_id:'V1',bank_account:'SHARED'},{vendor_id:'V2',bank_account:'SHARED'}],trigger_fields:['bank_account']}};
beforeEach(()=>{vi.resetAllMocks();masterDataApi.status.mockResolvedValue({data:[{dataset:'vendor-master',rows_loaded:2},{dataset:'employee-roster',rows_loaded:2},{dataset:'payroll-payments',rows_loaded:2}]});masterDataApi.findings.mockResolvedValue({data:{items:[]}});masterDataApi.run.mockResolvedValue({data:{items:[finding],statuses:[],config:{new_vendor_amount_inr:'2000000',new_vendor_days:7,salary_tolerance:'.05'}}});masterDataApi.send.mockResolvedValue({data:{case_id:42}});recordsApi.lookup.mockImplementation(async records=>({data:records.map(r=>({...r,exists:true}))}));});
afterEach(cleanup);
it('runs vendor checks, lists every involved vendor, and sends once to the unified case route',async()=>{
 const user=userEvent.setup();render(<MemoryRouter><MasterChecks dataset="vendor"/></MemoryRouter>);
 expect(screen.getByText(/Cannot evaluate, vendor-linked transactions unavailable/)).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'Recheck (optional)'}));
 expect(await screen.findByText('Two vendors share a bank account.')).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'View evidence'}));
 expect(await screen.findByRole('link',{name:'V2'})).toBeTruthy();
 expect(screen.getAllByText('bank account · Rule trigger')).toHaveLength(2);
 await user.click(screen.getByRole('button',{name:'Close evidence'}));
 await user.click(screen.getByRole('button',{name:'Send to review'}));
 const link=await screen.findByRole('link',{name:'Open case #42'});expect(link.getAttribute('href')).toContain('/review/cases/42');expect(masterDataApi.send).toHaveBeenCalledTimes(1);
});
it('shows import instructions when required datasets are missing and explains payroll limits',async()=>{
 masterDataApi.status.mockResolvedValue({data:[]});render(<MemoryRouter><MasterChecks dataset="payroll"/></MemoryRouter>);
 expect(await screen.findByText(/Import employee-roster, payroll-payments to enable this check/)).toBeTruthy();expect(screen.getByText(/PAN matching on roster only/)).toBeTruthy();
});
it('displays row rejection reports for partial imports and refreshes stored counts',async()=>{
 const user=userEvent.setup();masterDataApi.upload.mockResolvedValue({data:{dataset:'vendor-master',status:'partial',inserted:1,updated:0,skipped:0,rejected:1,errors:[{row:3,reason:'vendor_id cannot be blank'}]}});
 render(<MemoryRouter><MasterDataImport/></MemoryRouter>);await user.upload(screen.getByLabelText('CSV file'),new File(['vendor_id\nV1'],'vendors.csv',{type:'text/csv'}));
 expect(screen.getByLabelText('CSV file').files).toHaveLength(1);fireEvent.submit(screen.getByRole('button',{name:'Import and check'}).closest('form'));expect(await screen.findByText(/Row 3: vendor_id cannot be blank/)).toBeTruthy();expect(screen.getByText(/Inserted 1; updated 0; skipped 0; rejected 1/)).toBeTruthy();expect(masterDataApi.status.mock.calls.length).toBeGreaterThan(1);
});
it('keeps stale finding errors visible instead of creating a case',async()=>{
 masterDataApi.findings.mockResolvedValue({data:{items:[finding]}});masterDataApi.send.mockRejectedValue({response:{data:{detail:'Finding changed after re-import. Run checks again.'}}});render(<MemoryRouter><MasterChecks dataset="vendor"/></MemoryRouter>);
 await userEvent.click(await screen.findByRole('button',{name:'Send to review'}));expect(await screen.findByRole('alert')).toHaveProperty('textContent','Finding changed after re-import. Run checks again.');expect(screen.queryByRole('link',{name:'Open case #42'})).toBeNull();
});

it('imports bank transfers directly in the same form and shows automatic screening counts',async()=>{
 const user=userEvent.setup();transfersApi.upload.mockResolvedValue({data:{imported:10,skipped:0,checks:{status:'completed',stages:[{detector:'bank_transfers',status:'completed',circular_findings:1,reconciliation_findings:3}]}}});
 render(<MemoryRouter><MasterDataImport/></MemoryRouter>);await user.selectOptions(screen.getByLabelText('Dataset type'),'bank-transfers');await user.upload(screen.getByLabelText('CSV file'),new File(['transaction_id\nT1'],'transfers.csv',{type:'text/csv'}));fireEvent.submit(screen.getByRole('button',{name:'Import and check'}).closest('form'));
 expect(await screen.findByText(/1 cycles; 3 reconciliation findings/)).toBeTruthy();expect(transfersApi.upload).toHaveBeenCalledTimes(1);
});
it('imports a linked receipt in the combined form without requiring a second scoring action',async()=>{
 const user=userEvent.setup();claimsApi.uploadReceipt.mockResolvedValue({data:{upload_status:'processed',receipt_id:'R1',checks:{status:'completed',stages:[{detector:'expense_model',status:'completed',scored_count:1,flagged_count:1}]}}});render(<MemoryRouter><MasterDataImport/></MemoryRouter>);await user.selectOptions(screen.getByLabelText('Dataset type'),'receipts');await user.type(screen.getByLabelText('Target Claim ID'),'C1');await user.upload(screen.getByLabelText('Receipt image or PDF'),new File(['image'],'receipt.png',{type:'image/png'}));fireEvent.submit(screen.getByRole('button',{name:'Import and check'}).closest('form'));expect(await screen.findByText(/1 claims scored, 1 flagged/)).toBeTruthy();expect(claimsApi.uploadReceipt.mock.calls[0][0]).toBe('C1');
});
