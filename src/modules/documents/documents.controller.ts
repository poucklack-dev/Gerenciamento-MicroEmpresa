import {
  Controller,
  FileTypeValidator,
  MaxFileSizeValidator,
  ParseFilePipe,
  Post,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { StorageService } from '../../shared/storage/storage.service';
import { FilePayload } from '../../shared/storage/storage.interface';

@Controller('documents')
export class DocumentsController {
  constructor(private readonly storageService: StorageService) {}

  @Post('upload/contract')
  @UseInterceptors(FileInterceptor('file'))
  async uploadContract(
    @UploadedFile(
      new ParseFilePipe({
        validators: [
          new MaxFileSizeValidator({ maxSize: 10 * 1024 * 1024 }), // 10MB
          new FileTypeValidator({ fileType: 'application/pdf' }),
        ],
      }),
    )
    file: FilePayload,
  ) {
    // REGRA 4: A API do storage deve receber obrigatoriamente `subdir`
    const savedPath = await this.storageService.save(file, 'contratos');

    return {
      message: 'Contract uploaded successfully',
      path: savedPath,
      url: await this.storageService.getUrl(savedPath),
    };
  }

  @Post('upload/invoice')
  @UseInterceptors(FileInterceptor('file'))
  async uploadInvoice(
    @UploadedFile(new ParseFilePipe()) file: FilePayload,
  ) {
    // REGRA 7: Todas as rotas... usam ESSE mesmo service passando apenas o `subdir`
    const savedPath = await this.storageService.save(file, 'contas_pagar');
    
    return {
      message: 'Invoice uploaded successfully',
      path: savedPath,
      url: await this.storageService.getUrl(savedPath),
    };
  }
}
