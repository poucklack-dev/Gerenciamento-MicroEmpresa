import { BadRequestException, Inject, Injectable } from '@nestjs/common';
import { ConfigType } from '@nestjs/config';
import { v4 as uuidv4 } from 'uuid';
import * as path from 'path';
import storageConfig from '../../config/storage.config';
import { FilePayload, IStorageDriver } from './storage.interface';

@Injectable()
export class StorageService {
  constructor(
    @Inject('STORAGE_DRIVER') private readonly driver: IStorageDriver,
    @Inject(storageConfig.KEY)
    private config: ConfigType<typeof storageConfig>,
  ) {}

  /**
   * Saves a file to a specified subdirectory in the storage.
   * @param file The file payload from the request.
   * @param subdir The subdirectory to save the file in (e.g., 'contratos').
   * @returns The full path to the saved file.
   */
  async save(file: FilePayload, subdir: string): Promise<string> {
    this.validateSubdir(subdir);

    const sanitizedFilename = this.sanitizeFilename(file.originalname);
    const uniqueFilename = `${uuidv4()}-${sanitizedFilename}`;
    const filePath = path.join('uploads', subdir, uniqueFilename).replace(/\\/g, '/');

    this.validatePath(filePath);

    return this.driver.save(file, filePath);
  }

  /**
   * Deletes a file from the storage.
   * @param path The full path of the file to delete.
   */
  async delete(path: string): Promise<void> {
    this.validatePath(path);
    return this.driver.delete(path);
  }

  /**
   * Gets a public or signed URL for a file.
   * @param path The full path of the file.
   */
  getUrl(path: string): Promise<string> {
    this.validatePath(path);
    return this.driver.getUrl(path);
  }

  private sanitizeFilename(filename: string): string {
    // Basic sanitization, similar to werkzeug.secure_filename
    const cleaned = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
    // Prohibit leading dots or slashes
    if (cleaned.startsWith('.') || cleaned.startsWith('/') || cleaned.startsWith('\\')) {
      return `_${cleaned}`;
    }
    return cleaned;
  }

  private validateSubdir(subdir: string): void {
    if (!this.config.allowedSubdirs.includes(subdir)) {
      throw new BadRequestException(`Invalid subdir: ${subdir}.`);
    }
    if (subdir.includes('/') || subdir.includes('\\') || subdir.includes('..')) {
      throw new BadRequestException('Subdir cannot contain path traversal characters.');
    }
  }

  private validatePath(filePath: string): void {
    if (filePath.includes('..')) {
      throw new BadRequestException('Path cannot contain ".." characters.');
    }
  }
}
