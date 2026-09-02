export interface FilePayload {
  fieldname: string;
  originalname: string;
  encoding: string;
  mimetype: string;
  buffer: Buffer;
  size: number;
}

export interface IStorageDriver {
  /**
   * Saves a file to the storage.
   * @param file The file to save.
   * @param path The path (including filename) where the file should be saved.
   * @returns A promise that resolves to the full path of the saved file.
   */
  save(file: FilePayload, path: string): Promise<string>;

  /**
   * Deletes a file from the storage.
   * @param path The path of the file to delete.
   * @returns A promise that resolves when the file is deleted.
   */
  delete(path: string): Promise<void>;

  /**
   * Gets a public or signed URL for a file.
   * @param path The path of the file.
   * @returns A promise that resolves to the file's URL.
   */
  getUrl(path: string): Promise<string>;
}
