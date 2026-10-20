import { ApiError } from '../api/http.ts';
import type { PartnerEntityType, PartnerRequisites, PartnerRequisitesPayload, PartnerRequisitesWrite } from './types.ts';

export const emptyRequisitesDraft = (): PartnerRequisitesPayload => ({
    entity_type: 'self_employed', recipient_name: '', tax_id: '', kpp: null,
    bank_name: '', bic: '', correspondent_account: '', settlement_account: '',
});
const draftOf = (record: PartnerRequisites | null): PartnerRequisitesPayload => record ? {
    entity_type: record.entity_type, recipient_name: record.recipient_name, tax_id: record.tax_id,
    kpp: record.kpp ?? null, bank_name: record.bank_name, bic: record.bic,
    correspondent_account: record.correspondent_account, settlement_account: record.settlement_account,
} : emptyRequisitesDraft();
type Transport = {
    read: (signal: AbortSignal) => Promise<PartnerRequisites | null>;
    save: (draft: PartnerRequisitesWrite, signal: AbortSignal) => Promise<PartnerRequisites>;
};
type State = {
    account: string | null; loaded: boolean; record: PartnerRequisites | null;
    draft: PartnerRequisitesPayload; status: 'idle' | 'loading' | 'ready' | 'saving';
    error: unknown; saved: boolean; conflict: boolean; reloadFailed: boolean;
};
const empty = (account: string | null): State => ({account, loaded: false, record: null,
    draft: emptyRequisitesDraft(), status: 'idle', error: null, saved: false, conflict: false, reloadFailed: false});

/** Sensitive form state lives only in this account's mounted editor. */
export class RequisitesEditor {
    private state = empty(null);
    private listeners = new Set<() => void>();
    private transport: Transport | null = null;
    private controller: AbortController | null = null;
    private generation = 0;
    getSnapshot = () => this.state;
    subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
    private emit(patch: Partial<State>) { this.state = {...this.state, ...patch}; this.listeners.forEach(listener => listener()); }
    dispose = () => { this.generation++; this.controller?.abort(); this.controller = null; this.transport = null; };
    setAccount = (account: string | null, transport: Transport | null) => {
        this.dispose(); this.transport = account ? transport : null; this.state = empty(account); this.emit({});
    };
    cancelRead = () => {
        if (this.state.status !== 'loading') return;
        this.generation++; this.controller?.abort(); this.controller = null; this.emit({status:this.state.loaded ? 'ready' : 'idle', error:null});
    };
    private async perform(saving: boolean, forceRead = false) {
        const transport = this.transport;
        if (!transport || this.controller || (saving ? !this.state.loaded || this.state.conflict : this.state.loaded && !forceRead)) return false;
        const controller = new AbortController(), generation = this.generation;
        this.controller = controller;
        this.emit({status: saving ? 'saving' : 'loading', error:null, saved:false});
        try {
            const record = saving ? await transport.save({...structuredClone(this.state.draft), expected_version: this.state.record?.version ?? 0}, controller.signal) : await transport.read(controller.signal);
            if (controller.signal.aborted || generation !== this.generation) return false;
            if (saving && record === null) throw new Error('Сервер не подтвердил реквизиты.');
            this.emit({record, draft:draftOf(record), loaded:true, status:'ready', saved:saving, error:null, conflict:false, reloadFailed:false});
            return true;
        } catch (error) {
            if (controller.signal.aborted || generation !== this.generation) return false;
            this.emit({status:'ready', error, reloadFailed:forceRead,
                conflict:this.state.conflict || (saving && error instanceof ApiError && error.status === 409 && error.code === 'requisites_version_conflict')});
            return false;
        } finally { if (this.controller === controller) this.controller = null; }
    }
    load = () => this.perform(false);
    save = () => this.perform(true);
    reload = () => this.perform(false, true);
    setField = <Key extends keyof PartnerRequisitesPayload>(key: Key, value: PartnerRequisitesPayload[Key]) => {
        if (!this.transport || this.controller || !this.state.loaded || this.state.conflict) return;
        this.emit({draft:{...this.state.draft,[key]:value},saved:false,error:null});
    };
    setEntityType = (entity_type: PartnerEntityType) => {
        if (!this.transport || this.controller || !this.state.loaded || this.state.conflict) return;
        this.emit({draft:{...this.state.draft,entity_type,tax_id:'',kpp:entity_type==='legal_entity'?'':null},saved:false,error:null});
    };
}
