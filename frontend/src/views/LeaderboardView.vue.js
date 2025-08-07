"use strict";
/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
Object.defineProperty(exports, "__esModule", { value: true });
var vue_1 = require("vue");
var axios_1 = require("axios");
var leaderboardData = (0, vue_1.ref)([]);
var loading = (0, vue_1.ref)(true);
var error = (0, vue_1.ref)(null);
// This should be configured more robustly in a real app, e.g., via environment variables
var API_BASE_URL = 'http://localhost:8000/api/v1';
var fetchLeaderboard = function () { return __awaiter(void 0, void 0, void 0, function () {
    var response, err_1;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                _a.trys.push([0, 2, 3, 4]);
                return [4 /*yield*/, axios_1.default.get("".concat(API_BASE_URL, "/leaderboards/engagement?timeframe=24h&limit=50"))];
            case 1:
                response = _a.sent();
                leaderboardData.value = response.data.map(function (item, index) { return (__assign(__assign({}, item), { rank: index + 1 })); });
                return [3 /*break*/, 4];
            case 2:
                err_1 = _a.sent();
                console.error('Failed to fetch leaderboard:', err_1);
                error.value = 'Failed to load leaderboard data. Please try again later.';
                return [3 /*break*/, 4];
            case 3:
                loading.value = false;
                return [7 /*endfinally*/];
            case 4: return [2 /*return*/];
        }
    });
}); };
var onAvatarError = function (event) {
    // Replace broken avatar images with a default placeholder
    event.target.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxIDEiPjwvc3ZnPg==';
};
(0, vue_1.onMounted)(function () {
    fetchLeaderboard();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
var __VLS_ctx = {};
var __VLS_components;
var __VLS_directives;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "leaderboard" }));
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)(__assign({ class: "subtitle" }));
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "loading" }));
}
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "error" }));
    (__VLS_ctx.error);
}
if (__VLS_ctx.leaderboardData.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "leaderboard-grid" }));
    for (var _i = 0, _a = __VLS_getVForSourceType((__VLS_ctx.leaderboardData)); _i < _a.length; _i++) {
        var item = _a[_i][0];
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "leaderboard-item" }, { key: (item.did) }));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "rank" }));
        (item.rank);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "profile" }));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.img)(__assign(__assign({ onError: (__VLS_ctx.onAvatarError) }, { src: (item.avatar), alt: "avatar" }), { class: "avatar" }));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "profile-info" }));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)(__assign({ href: ("https://bsky.app/profile/".concat(item.did)), target: "_blank" }, { class: "display-name" }));
        (item.display_name || item.handle);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)(__assign({ class: "handle" }));
        (item.handle);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)(__assign({ class: "score" }));
        (item.score.toLocaleString());
    }
}
/** @type {__VLS_StyleScopedClasses['leaderboard']} */ ;
/** @type {__VLS_StyleScopedClasses['subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['loading']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['leaderboard-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['leaderboard-item']} */ ;
/** @type {__VLS_StyleScopedClasses['rank']} */ ;
/** @type {__VLS_StyleScopedClasses['profile']} */ ;
/** @type {__VLS_StyleScopedClasses['avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['profile-info']} */ ;
/** @type {__VLS_StyleScopedClasses['display-name']} */ ;
/** @type {__VLS_StyleScopedClasses['handle']} */ ;
/** @type {__VLS_StyleScopedClasses['score']} */ ;
var __VLS_dollars;
var __VLS_self = (await Promise.resolve().then(function () { return require('vue'); })).defineComponent({
    setup: function () {
        return {
            leaderboardData: leaderboardData,
            loading: loading,
            error: error,
            onAvatarError: onAvatarError,
        };
    },
});
exports.default = (await Promise.resolve().then(function () { return require('vue'); })).defineComponent({
    setup: function () {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
