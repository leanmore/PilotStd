// eslint-plugin-custom — 项目自定义 ESLint 规则集
import noRawI18nKey from './rules/no-raw-i18n-key.js';
import noSensitivePersist from './rules/no-sensitive-persist.js'
import noRawButton from './rules/no-raw-button.js';
import noRawInput from './rules/no-raw-input.js';
import noRawTable from './rules/no-raw-table.js';
import noRawCard from './rules/no-raw-card.js';

export default {
  rules: {
    'no-raw-i18n-key': noRawI18nKey,
    'no-sensitive-persist': noSensitivePersist,
    'no-raw-button': noRawButton,
    'no-raw-input': noRawInput,
    'no-raw-table': noRawTable,
    'no-raw-card': noRawCard,
  },
};
