/* --------------------------------------------------------------------------------------------
 * Copyright (c) Microsoft Corporation. All rights reserved.
 * Licensed under the MIT License. See License.txt in the project root for license information.
 * ------------------------------------------------------------------------------------------ */
'use strict';
var { Buffer } = require("contrib/buffer");
var { setTimeout, clearTimeout, setImmediate } = require("sdk/timers");
var __extends = (this && this.__extends) || (function () {
    var extendStatics = Object.setPrototypeOf ||
        ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
        function (d, b) { for (var p in b) if (b.hasOwnProperty(p)) d[p] = b[p]; };
    return function (d, b) {
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
var events_1 = require("./events");
var Is = require("./is");
var DefaultSize = 8192;
var CR = new Buffer('\r', 'ascii')[0];
var LF = new Buffer('\n', 'ascii')[0];
var CRLF = '\r\n';
var MessageBuffer = /** @class */ (function () {
    function MessageBuffer(encoding) {
        if (encoding === void 0) { encoding = 'utf8'; }
        this.encoding = encoding;
        this.index = 0;
        this.buffer = new Buffer(DefaultSize);
    }
    MessageBuffer.prototype.append = function (chunk) {
        var toAppend = chunk;
        if (typeof (chunk) == 'string') {
            var str = chunk;
            var bufferLen = Buffer.byteLength(str, this.encoding);
            toAppend = new Buffer(bufferLen);
            toAppend.write(str, 0, bufferLen, this.encoding);
        }
        if (this.buffer.length - this.index >= toAppend.length) {
            toAppend.copy(this.buffer, this.index, 0, toAppend.length);
        }
        else {
            var newSize = (Math.ceil((this.index + toAppend.length) / DefaultSize) + 1) * DefaultSize;
            if (this.index === 0) {
                this.buffer = new Buffer(newSize);
                toAppend.copy(this.buffer, 0, 0, toAppend.length);
            }
            else {
                this.buffer = Buffer.concat([this.buffer.slice(0, this.index), toAppend], newSize);
            }
        }
        this.index += toAppend.length;
    };
    MessageBuffer.prototype.tryReadHeaders = function () {
        var result = undefined;
        var current = 0;
        while (current + 3 < this.index && (this.buffer[current] !== CR || this.buffer[current + 1] !== LF || this.buffer[current + 2] !== CR || this.buffer[current + 3] !== LF)) {
            current++;
        }
        // No header / body separator found (e.g CRLFCRLF)
        if (current + 3 >= this.index) {
            return result;
        }
        result = Object.create(null);
        var headers = this.buffer.toString('ascii', 0, current).split(CRLF);
        headers.forEach(function (header) {
            var index = header.indexOf(':');
            if (index === -1) {
                throw new Error('Message header must separate key and value using :');
            }
            var key = header.substr(0, index);
            var value = header.substr(index + 1).trim();
            result[key] = value;
        });
        var nextStart = current + 4;
        this.buffer = this.buffer.slice(nextStart);
        this.index = this.index - nextStart;
        return result;
    };
    MessageBuffer.prototype.tryReadContent = function (length) {
        if (this.index < length) {
            return null;
        }
        var result = this.buffer.toString(this.encoding, 0, length);
        var nextStart = length;
        this.buffer.copy(this.buffer, 0, nextStart);
        this.index = this.index - nextStart;
        return result;
    };
    Object.defineProperty(MessageBuffer.prototype, "numberOfBytes", {
        get: function () {
            return this.index;
        },
        enumerable: true,
        configurable: true
    });
    return MessageBuffer;
}());
var MessageReader;
(function (MessageReader) {
    function is(value) {
        var candidate = value;
        return candidate && Is.func(candidate.listen) && Is.func(candidate.dispose) &&
            Is.func(candidate.onError) && Is.func(candidate.onClose) && Is.func(candidate.onPartialMessage);
    }
    MessageReader.is = is;
})(MessageReader = exports.MessageReader || (exports.MessageReader = {}));
var AbstractMessageReader = /** @class */ (function () {
    function AbstractMessageReader() {
        this.errorEmitter = new events_1.Emitter();
        this.closeEmitter = new events_1.Emitter();
        this.partialMessageEmitter = new events_1.Emitter();
    }
    AbstractMessageReader.prototype.dispose = function () {
        this.errorEmitter.dispose();
        this.closeEmitter.dispose();
    };
    Object.defineProperty(AbstractMessageReader.prototype, "onError", {
        get: function () {
            return this.errorEmitter.event;
        },
        enumerable: true,
        configurable: true
    });
    AbstractMessageReader.prototype.fireError = function (error) {
        this.errorEmitter.fire(this.asError(error));
    };
    Object.defineProperty(AbstractMessageReader.prototype, "onClose", {
        get: function () {
            return this.closeEmitter.event;
        },
        enumerable: true,
        configurable: true
    });
    AbstractMessageReader.prototype.fireClose = function () {
        this.closeEmitter.fire(undefined);
    };
    Object.defineProperty(AbstractMessageReader.prototype, "onPartialMessage", {
        get: function () {
            return this.partialMessageEmitter.event;
        },
        enumerable: true,
        configurable: true
    });
    AbstractMessageReader.prototype.firePartialMessage = function (info) {
        this.partialMessageEmitter.fire(info);
    };
    AbstractMessageReader.prototype.asError = function (error) {
        if (error instanceof Error) {
            return error;
        }
        else {
            return new Error("Reader recevied error. Reason: " + (Is.string(error.message) ? error.message : 'unknown'));
        }
    };
    return AbstractMessageReader;
}());
exports.AbstractMessageReader = AbstractMessageReader;
var StreamMessageReader = /** @class */ (function (_super) {
    __extends(StreamMessageReader, _super);
    function StreamMessageReader(readable, encoding) {
        if (encoding === void 0) { encoding = 'utf8'; }
        var _this = _super.call(this) || this;
        _this.readable = readable;
        _this.buffer = new MessageBuffer(encoding);
        _this._partialMessageTimeout = 10000;
        return _this;
    }
    Object.defineProperty(StreamMessageReader.prototype, "partialMessageTimeout", {
        get: function () {
            return this._partialMessageTimeout;
        },
        set: function (timeout) {
            this._partialMessageTimeout = timeout;
        },
        enumerable: true,
        configurable: true
    });
    StreamMessageReader.prototype.listen = function (callback) {
        var _this = this;
        this.nextMessageLength = -1;
        this.messageToken = 0;
        this.partialMessageTimer = undefined;
        this.callback = callback;
        this.readable.on('data', function (data) {
            _this.onData(data);
        });
        this.readable.on('error', function (error) { return _this.fireError(error); });
        this.readable.on('close', function () { return _this.fireClose(); });
    };
    StreamMessageReader.prototype.onData = function (data) {
        this.buffer.append(data);
        while (true) {
            if (this.nextMessageLength === -1) {
                var headers = this.buffer.tryReadHeaders();
                if (!headers) {
                    return;
                }
                var contentLength = headers['Content-Length'];
                if (!contentLength) {
                    throw new Error('Header must provide a Content-Length property.');
                }
                var length = parseInt(contentLength);
                if (isNaN(length)) {
                    throw new Error('Content-Length value must be a number.');
                }
                this.nextMessageLength = length;
                // Take the encoding form the header. For compatibility
                // treat both utf-8 and utf8 as node utf8
            }
            var msg = this.buffer.tryReadContent(this.nextMessageLength);
            if (msg === null) {
                /** We haven't recevied the full message yet. */
                this.setPartialMessageTimer();
                return;
            }
            this.clearPartialMessageTimer();
            this.nextMessageLength = -1;
            this.messageToken++;
            var json = JSON.parse(msg);
            this.callback(json);
        }
    };
    StreamMessageReader.prototype.clearPartialMessageTimer = function () {
        if (this.partialMessageTimer) {
            clearTimeout(this.partialMessageTimer);
            this.partialMessageTimer = undefined;
        }
    };
    StreamMessageReader.prototype.setPartialMessageTimer = function () {
        var _this = this;
        this.clearPartialMessageTimer();
        if (this._partialMessageTimeout <= 0) {
            return;
        }
        this.partialMessageTimer = setTimeout(function (token, timeout) {
            _this.partialMessageTimer = undefined;
            if (token === _this.messageToken) {
                _this.firePartialMessage({ messageToken: token, waitingTime: timeout });
                _this.setPartialMessageTimer();
            }
        }, this._partialMessageTimeout, this.messageToken, this._partialMessageTimeout);
    };
    return StreamMessageReader;
}(AbstractMessageReader));
exports.StreamMessageReader = StreamMessageReader;
var IPCMessageReader = /** @class */ (function (_super) {
    __extends(IPCMessageReader, _super);
    function IPCMessageReader(process) {
        var _this = _super.call(this) || this;
        _this.process = process;
        var eventEmitter = _this.process;
        eventEmitter.on('error', function (error) { return _this.fireError(error); });
        eventEmitter.on('close', function () { return _this.fireClose(); });
        return _this;
    }
    IPCMessageReader.prototype.listen = function (callback) {
        this.process.on('message', callback);
    };
    return IPCMessageReader;
}(AbstractMessageReader));
exports.IPCMessageReader = IPCMessageReader;
var SocketMessageReader = /** @class */ (function (_super) {
    __extends(SocketMessageReader, _super);
    function SocketMessageReader(socket, encoding) {
        if (encoding === void 0) { encoding = 'utf-8'; }
        return _super.call(this, socket, encoding) || this;
    }
    return SocketMessageReader;
}(StreamMessageReader));
exports.SocketMessageReader = SocketMessageReader;
