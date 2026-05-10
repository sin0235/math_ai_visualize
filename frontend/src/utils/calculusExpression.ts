export type CompiledExpression = {
  source: string;
  evaluate: (x: number) => number;
};

type Token =
  | { type: 'number'; value: number }
  | { type: 'identifier'; value: string }
  | { type: 'operator'; value: '+' | '-' | '*' | '/' | '^' }
  | { type: 'paren'; value: '(' | ')' }
  | { type: 'comma'; value: ',' };

type RpnToken =
  | { type: 'number'; value: number }
  | { type: 'variable' }
  | { type: 'operator'; value: '+' | '-' | '*' | '/' | '^' | 'neg' }
  | { type: 'function'; value: FunctionName };

type FunctionName = keyof typeof FUNCTIONS;

const FUNCTIONS = {
  sqrt: (a: number) => Math.sqrt(a),
  abs: (a: number) => Math.abs(a),
  sin: (a: number) => Math.sin(a),
  cos: (a: number) => Math.cos(a),
  tan: (a: number) => Math.tan(a),
  exp: (a: number) => Math.exp(a),
  ln: (a: number) => Math.log(a),
  log: (a: number, base?: number) => base === undefined ? Math.log(a) : Math.log(a) / Math.log(base),
  asin: (a: number) => Math.asin(a),
  acos: (a: number) => Math.acos(a),
  atan: (a: number) => Math.atan(a),
  min: (a: number, b: number) => Math.min(a, b),
  max: (a: number, b: number) => Math.max(a, b),
} as const;

const FUNCTION_ARITY: Record<FunctionName, 1 | 2 | 'variable'> = {
  sqrt: 1,
  abs: 1,
  sin: 1,
  cos: 1,
  tan: 1,
  exp: 1,
  ln: 1,
  log: 'variable',
  asin: 1,
  acos: 1,
  atan: 1,
  min: 2,
  max: 2,
};

const PRECEDENCE: Record<string, number> = { '+': 1, '-': 1, '*': 2, '/': 2, '^': 3, neg: 4 };
const RIGHT_ASSOC = new Set(['^', 'neg']);

export function compileExpression(source: string): CompiledExpression {
  const trimmed = normalizeExpression(source);
  if (!trimmed) throw new Error('Vui lòng nhập biểu thức hàm số.');
  const tokens = tokenize(trimmed);
  const rpn = toRpn(tokens);
  return {
    source: trimmed,
    evaluate: (x: number) => evaluateRpn(rpn, x),
  };
}

export function normalizeExpression(source: string) {
  return source
    .trim()
    .replace(/\s+/g, '')
    .replace(/√/g, 'sqrt')
    .replace(/π/g, 'pi')
    .replace(/−/g, '-')
    .replace(/,/g, ',');
}

function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < source.length) {
    const char = source[i];
    if (/\d|\./.test(char)) {
      let end = i + 1;
      while (end < source.length && /[\d.]/.test(source[end])) end += 1;
      if (source[end]?.toLowerCase() === 'e') {
        let expEnd = end + 1;
        if (source[expEnd] === '+' || source[expEnd] === '-') expEnd += 1;
        while (expEnd < source.length && /\d/.test(source[expEnd])) expEnd += 1;
        if (expEnd > end + 1) end = expEnd;
      }
      const value = Number(source.slice(i, end));
      if (!Number.isFinite(value)) throw new Error(`Số không hợp lệ tại vị trí ${i + 1}.`);
      tokens.push({ type: 'number', value });
      i = end;
      continue;
    }
    if (/[a-zA-Z_]/.test(char)) {
      let end = i + 1;
      while (end < source.length && /[a-zA-Z_0-9]/.test(source[end])) end += 1;
      tokens.push({ type: 'identifier', value: source.slice(i, end).toLowerCase() });
      i = end;
      continue;
    }
    if (char === '+' || char === '-' || char === '*' || char === '/' || char === '^') {
      tokens.push({ type: 'operator', value: char });
      i += 1;
      continue;
    }
    if (char === '(' || char === ')') {
      tokens.push({ type: 'paren', value: char });
      i += 1;
      continue;
    }
    if (char === ',') {
      tokens.push({ type: 'comma', value: ',' });
      i += 1;
      continue;
    }
    throw new Error(`Ký tự “${char}” chưa được hỗ trợ.`);
  }
  return insertImplicitMultiplication(tokens);
}

function insertImplicitMultiplication(tokens: Token[]) {
  const output: Token[] = [];
  tokens.forEach((token, index) => {
    const prev = tokens[index - 1];
    if (prev && needsImplicitMultiply(prev, token)) output.push({ type: 'operator', value: '*' });
    output.push(token);
  });
  return output;
}

function needsImplicitMultiply(prev: Token, next: Token) {
  const prevValue = prev.type === 'number' || prev.type === 'identifier' || (prev.type === 'paren' && prev.value === ')');
  const nextValue = next.type === 'number' || next.type === 'identifier' || (next.type === 'paren' && next.value === '(');
  if (!prevValue || !nextValue) return false;
  if (prev.type === 'identifier' && next.type === 'paren' && next.value === '(' && isFunction(prev.value)) return false;
  return true;
}

function toRpn(tokens: Token[]): RpnToken[] {
  const output: RpnToken[] = [];
  const stack: Array<Token | { type: 'function'; value: FunctionName }> = [];
  let prev: Token | null = null;

  tokens.forEach((token) => {
    if (token.type === 'number') output.push(token);
    else if (token.type === 'identifier') {
      if (token.value === 'x') output.push({ type: 'variable' });
      else if (token.value === 'pi') output.push({ type: 'number', value: Math.PI });
      else if (token.value === 'e') output.push({ type: 'number', value: Math.E });
      else if (isFunction(token.value)) stack.push({ type: 'function', value: token.value });
      else throw new Error(`Tên “${token.value}” chưa được hỗ trợ. Chỉ dùng biến x và các hàm phổ biến.`);
    } else if (token.type === 'comma') {
      while (stack.length && !(stack[stack.length - 1].type === 'paren' && stack[stack.length - 1].value === '(')) {
        pushStackOperator(output, stack.pop()!);
      }
      if (!stack.length) throw new Error('Dấu phẩy trong hàm không hợp lệ.');
    } else if (token.type === 'operator') {
      const op = token.value === '-' && (!prev || prev.type === 'operator' || prev.type === 'comma' || (prev.type === 'paren' && prev.value === '(')) ? 'neg' : token.value;
      while (stack.length) {
        const top = stack[stack.length - 1];
        if (top.type !== 'operator') break;
        const topOp = top.value;
        if ((RIGHT_ASSOC.has(op) && PRECEDENCE[op] < PRECEDENCE[topOp]) || (!RIGHT_ASSOC.has(op) && PRECEDENCE[op] <= PRECEDENCE[topOp])) {
          pushStackOperator(output, stack.pop()!);
        } else break;
      }
      stack.push({ type: 'operator', value: op as '+' | '-' | '*' | '/' | '^' });
    } else if (token.type === 'paren' && token.value === '(') stack.push(token);
    else if (token.type === 'paren' && token.value === ')') {
      while (stack.length && !(stack[stack.length - 1].type === 'paren' && stack[stack.length - 1].value === '(')) {
        pushStackOperator(output, stack.pop()!);
      }
      if (!stack.length) throw new Error('Thiếu dấu ngoặc mở.');
      stack.pop();
      if (stack[stack.length - 1]?.type === 'function') pushStackOperator(output, stack.pop()!);
    }
    prev = token;
  });

  while (stack.length) {
    const top = stack.pop()!;
    if (top.type === 'paren') throw new Error('Thiếu dấu ngoặc đóng.');
    pushStackOperator(output, top);
  }
  return output;
}

function pushStackOperator(output: RpnToken[], token: Token | { type: 'function'; value: FunctionName }) {
  if (token.type === 'operator') output.push({ type: 'operator', value: token.value });
  else if (token.type === 'function') output.push(token);
}

function evaluateRpn(tokens: RpnToken[], x: number) {
  const stack: number[] = [];
  tokens.forEach((token) => {
    if (token.type === 'number') stack.push(token.value);
    else if (token.type === 'variable') stack.push(x);
    else if (token.type === 'operator') {
      if (token.value === 'neg') {
        const a = popNumber(stack);
        stack.push(-a);
        return;
      }
      const b = popNumber(stack);
      const a = popNumber(stack);
      if (token.value === '+') stack.push(a + b);
      if (token.value === '-') stack.push(a - b);
      if (token.value === '*') stack.push(a * b);
      if (token.value === '/') stack.push(a / b);
      if (token.value === '^') stack.push(Math.pow(a, b));
    } else if (token.type === 'function') {
      const arity = FUNCTION_ARITY[token.value];
      if (arity === 2) {
        const b = popNumber(stack);
        const a = popNumber(stack);
        stack.push(FUNCTIONS[token.value](a, b));
      } else if (arity === 'variable' && token.value === 'log' && stack.length >= 2) {
        const b = popNumber(stack);
        const a = popNumber(stack);
        stack.push(FUNCTIONS.log(a, b));
      } else {
        const a = popNumber(stack);
        stack.push((FUNCTIONS[token.value] as (value: number) => number)(a));
      }
    }
  });
  if (stack.length !== 1) throw new Error('Biểu thức chưa hợp lệ.');
  return stack[0];
}

function popNumber(stack: number[]) {
  const value = stack.pop();
  if (value === undefined) throw new Error('Biểu thức thiếu toán hạng.');
  return value;
}

function isFunction(name: string): name is FunctionName {
  return Object.prototype.hasOwnProperty.call(FUNCTIONS, name);
}
