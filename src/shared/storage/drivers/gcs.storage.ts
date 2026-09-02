import { Storage } from '@google-cloud/storage';
import { Inject, Injectable, OnModuleInit } from '@nestjs/common';
import { ConfigType } from '@nestjs/config';
import storageConfig from '../../../config/storage.config';
import { FilePayload, IStorageDriver } from '../storage.interface';

@Injectable()
export class GcsStorage implements IStorageDriver, OnModuleInit {
  private storage: Storage;
  private bucketName: string;

  constructor(
    @Inject(storageConfig.KEY)
    private config: ConfigType<typeof storageConfig>,
  ) {
    this.bucketName = this.config.gcs.bucket;
  }

  onModuleInit() {
    this.storage = new Storage({
      projectId: this.config.gcs.projectId,
      credentials: this.config.gcs.credentials,
    });
  }

  async save(file: FilePayload, path: string): Promise<string> {
    const bucket = this.storage.bucket(this.bucketName);
    const blob = bucket.file(path);
    await blob.save(file.buffer, {
      contentType: file.mimetype,
    });
    return path;
  }

  async delete(path: string): Promise<void> {
    await this.storage.bucket(this.bucketName).file(path).delete({ ignoreNotFound: true });
  }

  async getUrl(path: string): Promise<string> {
    const [url] = await this.storage
      .bucket(this.bucketName)
      .file(path)
      .getSignedUrl({
        action: 'read',
        expires: Date.now() + 15 * 60 * 1000, // 15 minutes
      });
    return url;
  }
}
