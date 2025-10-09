import { ComponentCategory } from '../src/core/component';
import { PkgIdentify } from '../src/core/deps/pkg_identify';

const pkgNames = [
    'long',
    '@alipay/afservicesdk',
    '@xmpp/base64',
    '@xmpp/error',
    '@xmpp/event',
    '@xmpp/id',
    '@xmpp/jid',
    'base-64',
    'base64-js',
    'bignumber.js',
    'class-transformer',
    'eventemitter3',
    'koa-compose',
    'mime',
    'reflect-metadata',
    'protobufjs',
    '@protobufjs/aspromise',
    '@protobufjs/base64',
    '@protobufjs/codegen',
    '@protobufjs/eventemitter',
    '@protobufjs/fetch',
    '@protobufjs/float',
    '@protobufjs/inquire',
    '@protobufjs/path',
    '@protobufjs/pool',
    '@protobufjs/utf8',
    '@msgpack/msgpack',
    'rxjs',
    'sasl-anonymous',
    'saslmechanisms',
    'sasl-plain',
    'tslib',
];

async function main() {
    let pkgIdentify = PkgIdentify.getInstance();
    for (const pkg of pkgNames) {
        await pkgIdentify.validXpmPackage({name: pkg, kind: ComponentCategory.APP_LIB}, true);
    }
    pkgIdentify.save('./');
}

(async function () {
    await main();
})();