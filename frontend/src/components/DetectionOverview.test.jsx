// @vitest-environment jsdom
import React from 'react';
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import DetectionOverview from './DetectionOverview';
import {detectionApi} from '../api/client';
vi.mock('../api/client',()=>({detectionApi:{overview:vi.fn()}}));afterEach(cleanup);
it('counts master findings together while labelling their different units and separating model cohorts',async()=>{
 detectionApi.overview.mockResolvedValue({data:{total_review_signals:124,definition:'Review signals, not unique entities.',incomplete:false,errors:[],breakdown:[{detector:'Expense claims',findings:100,unit:'claims',source_records:1000,url:'/claims'},{detector:'Vendor rules',findings:10,unit:'rule findings',source_records:39,url:'/audit-screens?tab=vendor'},{detector:'Payroll rules',findings:14,unit:'rule findings',source_records:40,url:'/audit-screens?tab=payroll'}],cohorts:[{name:'Aster expense claims',claims:1000,scored:1000,policy_evaluated:1000,comparison_claims:1000,modes:{model_only:{available:1000,flagged:100,metrics:{precision:.5,recall:.6,f1:.5454,average_precision:.8,precision_at_k:{100:.9}}},policy_only:{available:1000,flagged:80,metrics:{precision:.4,recall:.3,f1:.3429}},combined:{available:1000,flagged:150,metrics:{precision:.45,recall:.7,f1:.5478}}}}],metric_scope:'Separate labelled expense cohorts'}});
 render(<MemoryRouter><DetectionOverview/></MemoryRouter>);expect(await screen.findByText(/124 review signals across all datasets/)).toBeTruthy();expect(screen.getByRole('link',{name:'Vendor rules'})).toBeTruthy();expect(screen.getByRole('link',{name:'Payroll rules'})).toBeTruthy();expect(screen.getByText('Aster expense claims')).toBeTruthy();expect(screen.getByText('90.00%')).toBeTruthy();expect(screen.getByText('Model-only')).toBeTruthy();expect(screen.getByText('Policy-only')).toBeTruthy();expect(screen.getByText('Combined (model OR policy)')).toBeTruthy();expect(screen.getAllByText('Not applicable')).toHaveLength(4);expect(screen.getByText('150')).toBeTruthy();
});
it('separates the split-test report from loaded diagnostics and marks enterprise ML disabled',async()=>{
 detectionApi.overview.mockResolvedValue({data:{total_review_signals:0,definition:'Signals',errors:[],breakdown:[],metric_scope:'Loaded diagnostics include training rows',benchmark:{scope:'Group-held-out synthetic evaluation',run_id:'run-1',limitations:['Previously inspected source'],results:{aster:{test:{threshold:.4866,rows:419,tp:20,fp:12,fn:0,precision:.625,recall:1,f1:.7692},test_average_precision:.8618}}},cohorts:[{name:'Enterprise',claims:10,scored:0,policy_evaluated:10,comparison_claims:10,strategy:{model_enabled:false},modes:{model_only:{disabled:true,metrics:{}}}}]}});
 render(<MemoryRouter><DetectionOverview/></MemoryRouter>);
 expect(await screen.findByText('Separate split-test results')).toBeTruthy();
 expect(screen.getByText('62.50%')).toBeTruthy();
 expect(screen.getByText('Model-only (disabled)')).toBeTruthy();
 expect(screen.getByText(/Training rows are excluded from this table/)).toBeTruthy();
});
