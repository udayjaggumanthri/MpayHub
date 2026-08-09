import { deriveFormReceiptIdentity, deriveReceiptIdentity, pickPrimaryIdentity } from './bbpsBillsHelpers';

describe('BBPS receipt identity', () => {
  test('electricity uses Service Number from input_params', () => {
    const identity = deriveReceiptIdentity({
      billType: 'Electricity',
      input_params: [{ paramName: 'Service Number', paramValue: '115654G310002173' }],
      customer_details: { 'Service Number': '115654G310002173' },
    });
    expect(identity).toEqual({
      label: 'Service Number',
      value: '115654G310002173',
    });
  });

  test('CustomerId humanizes to Customer ID', () => {
    const identity = deriveReceiptIdentity({
      billType: 'broadband-postpaid',
      input_params: [{ paramName: 'CustomerId', paramValue: 'h696077' }],
    });
    expect(identity).toEqual({
      label: 'Customer ID',
      value: 'h696077',
    });
  });

  test('prefers receipt_details identity from API', () => {
    const identity = deriveReceiptIdentity({
      billType: 'Electricity',
      receipt_details: {
        identity_label: 'Service Number',
        identity_value: '115654G310002173',
      },
      input_params: [],
    });
    expect(identity).toEqual({
      label: 'Service Number',
      value: '115654G310002173',
    });
  });

  test('prefers Service Number over agent mobile in customer_details', () => {
    const identity = deriveReceiptIdentity({
      category: 'electricity',
      inputParams: [
        { paramName: 'Service Number', paramValue: '115654G310002173' },
        { paramName: 'Mobile Number', paramValue: '9876543210' },
      ],
    });
    expect(identity.label).toBe('Service Number');
    expect(identity.value).toBe('115654G310002173');
  });

  test('credit card uses last 4 digits label', () => {
    const identity = deriveReceiptIdentity({
      billType: 'Credit Card',
      input_params: [{ paramName: 'Card Last 4 Digits', paramValue: '1234' }],
    });
    expect(identity).toEqual({
      label: 'Card Number (Last 4)',
      value: '1234',
    });
  });

  test('fastag uses vehicle number', () => {
    const identity = deriveReceiptIdentity({
      billType: 'FASTag',
      input_params: [{ paramName: 'Vehicle Number', paramValue: 'AP09AB1234' }],
    });
    expect(identity).toEqual({
      label: 'Vehicle Number',
      value: 'AP09AB1234',
    });
  });

  test('form identity reads MDM schema param names', () => {
    const identity = deriveFormReceiptIdentity({
      category: 'electricity',
      inputSchema: [
        {
          param_name: 'Service Number',
          display_label: 'Service Number',
          is_optional: false,
          send_in_input_params: true,
        },
      ],
      inputValues: { 'Service Number': '115654G310002173' },
    });
    expect(identity).toEqual({
      label: 'Service Number',
      value: '115654G310002173',
    });
  });

  test('pickPrimaryIdentity skips plan id', () => {
    const primary = pickPrimaryIdentity({
      inputParams: [
        { paramName: 'Plan ID', paramValue: 'PLN1' },
        { paramName: 'CA Number', paramValue: '998877' },
      ],
    });
    expect(primary).toEqual({ label: 'CA Number', value: '998877' });
  });
});
