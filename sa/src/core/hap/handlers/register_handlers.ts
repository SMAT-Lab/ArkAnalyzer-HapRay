/*
 * Register built-in handlers for folder, extension, and magic detection.
 */
import { HandlerRegistry } from '../registry';
import { DefaultExtensionHandler } from './extension_handlers';
import { DefaultFolderHandler } from './folder_handlers';
import { ZipMagicHandler } from './magic_handlers';
import { GenericArchiveFileHandler, SoFileHandler, JsBundleFileHandler, HermesBytecodeFileHandler, JsFileHandler, DefaultResourceFileHandler } from './special_file_handlers';

export function registerBuiltInHandlers(): void {
    const registry = HandlerRegistry.getInstance();
    registry.registerExtension(new DefaultExtensionHandler());
    registry.registerFolder(new DefaultFolderHandler());
    registry.registerMagic(new ZipMagicHandler());
    // file handlers for specific suffixes
    registry.registerFile(new SoFileHandler());
    registry.registerFile(new GenericArchiveFileHandler());
    registry.registerFile(new HermesBytecodeFileHandler());
    registry.registerFile(new JsBundleFileHandler());
    registry.registerFile(new JsFileHandler());
    registry.registerFile(new DefaultResourceFileHandler());
}


