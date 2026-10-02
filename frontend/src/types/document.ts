export type DocumentStatus =
  | 'new'
  | 'processing'
  | 'processed'
  | 'needs_review'
  | 'error'
  | 'sent';

export interface DocumentFile {
  filename: string;
  file_format: 'pdf' | 'xml';
}

export interface Debtor {
  name: string;
  inn?: string;
}

export interface Document {
  id: number;
  filename: string;
  documentType: string;
  caseNumber?: string;
  enforcementNumber?: string;

  status: DocumentStatus;
  createdAt: string;

  summary: string;

  // Техническая ручная проверка
  needsReview: boolean;
  reviewReason?: string;

  // Юридическая маршрутизация
  requiresLegalAction: boolean;
  legalActionReason?: string;
  evidenceFragment?: string;

  files: DocumentFile[];

  debtor?: string;
  amount?: number;

  fileFormat: 'pdf' | 'xml';
}