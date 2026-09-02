import { registerAs } from '@nestjs/config';

export const allowedSubdirs = [
  'contas_pagar',
  'contratos',
  'custos',
  'documentos',
  'equipe_campo',
  'faces',
  'fornecedores',
  'recebimentos',
];

export type StorageDriver = 'local' | 'gcs';

export default registerAs('storage', () => ({
  driver: (process.env.STORAGE_DRIVER || 'local') as StorageDriver,
  
  local: {
    path: process.env.LOCAL_STORAGE_PATH || './uploads',
  },
  
  gcs: {
    bucket: process.env.GCS_BUCKET,
    projectId: process.env.GCS_PROJECT_ID,
    credentials: {
      client_email: process.env.GCS_CLIENT_EMAIL,
      private_key: process.env.GCS_PRIVATE_KEY?.replace(/\\n/g, '\n'),
    },
  },

  allowedSubdirs: allowedSubdirs,
}));
