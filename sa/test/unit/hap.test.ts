import { describe, expect, it } from 'vitest';
import { Hap } from '../../src/core/hap/hap_parser';
import path from 'path';

describe('HapParserTest', () => {
    it('extract', async () => {
        let hapParser = await Hap.loadFromHap(path.join(__dirname, '../resources/test.hap'));
        expect(hapParser.bundleName).eq('com.example.downloadnotification');
        expect(hapParser.appName).eq('DownloadNotification');
    });
});
