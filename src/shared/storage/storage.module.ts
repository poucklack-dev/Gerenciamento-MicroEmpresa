import { Module, Provider } from '@nestjs/common';
import { ConfigModule, ConfigType } from '@nestjs/config';
import storageConfig from '../../config/storage.config';
import { GcsStorage } from './drivers/gcs.storage';
import { LocalStorage } from './drivers/local.storage';
import { StorageService } from './storage.service';

const storageProvider: Provider = {
  provide: 'STORAGE_DRIVER',
  useFactory: (
    config: ConfigType<typeof storageConfig>,
    local: LocalStorage,
    gcs: GcsStorage,
  ) => {
    if (config.driver === 'gcs') {
      return gcs;
    }
    return local;
  },
  inject: [storageConfig.KEY, LocalStorage, GcsStorage],
};

@Module({
  imports: [ConfigModule.forFeature(storageConfig)],
  providers: [StorageService, storageProvider, LocalStorage, GcsStorage],
  exports: [StorageService],
})
export class StorageModule {}
