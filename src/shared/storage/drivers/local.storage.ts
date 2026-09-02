import { Inject, Injectable } from '@nestjs/common';
import { ConfigType } from '@nestjs/config';
import * as fs from 'fs/promises';
import * as path from 'path';
import storageConfig from '../../../config/storage.config';
import { FilePayload, IStorageDriver } from '../storage.interface';

@Injectable()
export class LocalStorage implements IStorageDriver {
  private readonly basePath: string;

  constructor(
    @Inject(storageConfig.KEY)
    private config: ConfigType<typeof storageConfig>,
  ) {
    this.basePath = this.config.local.path;
  }

  async save(file: FilePayload, filePath: string): Promise<string> {
    const absolutePath = path.join(this.basePath, filePath);
    const directory = path.dirname(absolutePath);

    await fs.mkdir(directory, { recursive: true });
    await fs.writeFile(absolutePath, file.buffer);

    return filePath; // returns relative path like 'uploads/contratos/file.pdf'
  }

  async delete(filePath: string): Promise<void> {
    const absolutePath = path.join(this.basePath, filePath);
    try {
      await fs.unlink(absolutePath);
    } catch (error) {
      // Handle file not found error gracefully
      if (error.code !== 'ENOENT') {
        throw error;
      }
    }
  }

  async getUrl(filePath: string): Promise<string> {
    // In a real app, this would be a URL pointing to a static file server
    return `/static/${filePath}`;
  }
}
