// eslint-plugin-custom — 项目自定义 ESLint 规则集
import noRawI18nKey from './rules/no-raw-i18n-key.js';
import noSensitivePersist from './rules/no-sensitive-persist.js';

export default {
  rules: {
    'no-raw-i18n-key': noRawI18nKey,
    'no-sensitive-persist': noSensitivePersist,
  },
};
