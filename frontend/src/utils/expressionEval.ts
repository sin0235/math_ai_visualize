/**
 * Safe single-line math expression evaluator (frontend).
 *
 * Mirror của backend `expression_eval.py`. Dùng để eval các biểu thức toạ độ
 * khi parameter slider thay đổi: "a/2", "sqrt(3)*a/2", "h*sin(rad(alpha))"...
 *
 * An toàn: tự parse với regex tokenizer + recursive descent. KHÔNG dùng `eval`,
 * `Function`, `with`. Chỉ cho phép số, biến whitelisted, hàm whitelisted, và
 * các toán tử + - * / % ** //.
 */

const FUNCS: Record<string, (...args: number[]) => number> = {
  sqrt: Math.sqrt,
  sin: Math.sin,
  cos: Math.cos,
  tan: Math.tan,
  asin: Math.asin,
  acos: Math.acos,
  atan: Math.atan,
  atan2: (y, x) => Math.atan2(y, x),
  log: Math.log,
  log2: Math.log2,
  log10: Math.log10,
  exp: Math.exp,
  abs: Math.abs,
  min: (...args) => Math.min(...args),
  max: (...args) => Math.max(...args),
  floor: Math.floor,
  ceil: Math.ceil,
  round: Math.round,
  pow: (a, b) => Math.pow(a, b),
  deg: (x) => (x * 180) / Math.PI,
  rad: (x) => (x * Math.PI) / 180,
};

const CONSTS: Record<string, number> = {
  pi: Math.PI,
  e: Math.E,
};

type Token =
  | { type: 'num'; value: number }
  | { type: 'name'; value: string }
  | { type: 'op'; value: string }
  | { type: 'lparen' }
  | { type: 'rparen' }
  | { type: 'comma' };

function tokenize(expr: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  const n = expr.length;
  while (i < n) {
    const ch = expr[i];
    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
      i += 1;
      continue;
    }
    if ((ch >= '0' && ch <= '9') || ch === '.') {
      let j = i;
      let hasDot = ch === '.';
      while (j < n) {
        const c = expr[j + 1];
        if (c >= '0' && c <= '9') {
          j += 1;
        } else if (c === '.' && !hasDot) {
          hasDot = true;
          j += 1;
        } else if ((c === 'e' || c === 'E') && j + 1 < n) {
          j += 1;
          if (expr[j + 1] === '+' || expr[j + 1] === '-') j += 1;
        } else {
          break;
        }
      }
      const slice = expr.slice(i, j + 1);
      const num = Number(slice);
      if (!Number.isFinite(num)) throw new Error(`Số không hợp lệ: ${slice}`);
      tokens.push({ type: 'num', value: num });
      i = j + 1;
      continue;
    }
    if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch === '_') {
      let j = i;
      while (j + 1 < n) {
        const c = expr[j + 1];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c === '_') {
          j += 1;
        } else {
          break;
        }
      }
      tokens.push({ type: 'name', value: expr.slice(i, j + 1) });
      i = j + 1;
      continue;
    }
    if (ch === '(') {
      tokens.push({ type: 'lparen' });
      i += 1;
      continue;
    }
    if (ch === ')') {
      tokens.push({ type: 'rparen' });
      i += 1;
      continue;
    }
    if (ch === ',') {
      tokens.push({ type: 'comma' });
      i += 1;
      continue;
    }
    if (ch === '*' && expr[i + 1] === '*') {
      tokens.push({ type: 'op', value: '**' });
      i += 2;
      continue;
    }
    if (ch === '/' && expr[i + 1] === '/') {
      tokens.push({ type: 'op', value: '//' });
      i += 2;
      continue;
    }
    if ('+-*/%'.includes(ch)) {
      tokens.push({ type: 'op', value: ch });
      i += 1;
      continue;
    }
    throw new Error(`Ký tự không cho phép: ${ch}`);
  }
  return tokens;
}

class Parser {
  private pos = 0;

  constructor(private readonly tokens: Token[], private readonly vars: Record<string, number>) {}

  private peek(): Token | undefined {
    return this.tokens[this.pos];
  }

  private consume(): Token {
    const tok = this.tokens[this.pos];
    if (!tok) throw new Error('Hết token, expression không đầy đủ');
    this.pos += 1;
    return tok;
  }

  parseExpression(): number {
    const value = this.parseAddSub();
    if (this.pos < this.tokens.length) {
      throw new Error(`Token thừa: ${JSON.stringify(this.tokens[this.pos])}`);
    }
    return value;
  }

  private parseAddSub(): number {
    let left = this.parseMulDiv();
    while (true) {
      const tok = this.peek();
      if (tok?.type === 'op' && (tok.value === '+' || tok.value === '-')) {
        this.consume();
        const right = this.parseMulDiv();
        left = tok.value === '+' ? left + right : left - right;
      } else {
        break;
      }
    }
    return left;
  }

  private parseMulDiv(): number {
    let left = this.parseUnary();
    while (true) {
      const tok = this.peek();
      if (tok?.type === 'op' && (tok.value === '*' || tok.value === '/' || tok.value === '%' || tok.value === '//')) {
        this.consume();
        const right = this.parseUnary();
        if (tok.value === '*') left = left * right;
        else if (tok.value === '/') {
          if (right === 0) throw new Error('Chia 0');
          left = left / right;
        } else if (tok.value === '//') {
          if (right === 0) throw new Error('Chia 0');
          left = Math.floor(left / right);
        } else {
          if (right === 0) throw new Error('Modulo 0');
          left = left % right;
        }
      } else {
        break;
      }
    }
    return left;
  }

  private parseUnary(): number {
    const tok = this.peek();
    if (tok?.type === 'op' && (tok.value === '+' || tok.value === '-')) {
      this.consume();
      const v = this.parseUnary();
      return tok.value === '-' ? -v : v;
    }
    return this.parsePower();
  }

  private parsePower(): number {
    const left = this.parsePrimary();
    const tok = this.peek();
    if (tok?.type === 'op' && tok.value === '**') {
      this.consume();
      // right-associative
      const right = this.parseUnary();
      return Math.pow(left, right);
    }
    return left;
  }

  private parsePrimary(): number {
    const tok = this.consume();
    if (tok.type === 'num') return tok.value;
    if (tok.type === 'lparen') {
      const v = this.parseAddSub();
      const next = this.consume();
      if (next.type !== 'rparen') throw new Error('Thiếu )');
      return v;
    }
    if (tok.type === 'name') {
      const next = this.peek();
      if (next?.type === 'lparen') {
        this.consume();
        const fn = FUNCS[tok.value];
        if (!fn) throw new Error(`Hàm không cho phép: ${tok.value}`);
        const args: number[] = [];
        if (this.peek()?.type !== 'rparen') {
          args.push(this.parseAddSub());
          while (this.peek()?.type === 'comma') {
            this.consume();
            args.push(this.parseAddSub());
          }
        }
        const close = this.consume();
        if (close.type !== 'rparen') throw new Error('Thiếu )');
        return fn(...args);
      }
      if (tok.value in CONSTS) return CONSTS[tok.value];
      if (tok.value in this.vars) return this.vars[tok.value];
      throw new Error(`Biến chưa khai báo: ${tok.value}`);
    }
    throw new Error(`Token không hợp lệ: ${JSON.stringify(tok)}`);
  }
}

export function safeEvalExpression(expr: string, variables: Record<string, number> = {}): number {
  if (typeof expr !== 'string' || !expr.trim()) throw new Error('Expression rỗng');
  const tokens = tokenize(expr);
  if (tokens.length === 0) throw new Error('Expression rỗng');
  const parser = new Parser(tokens, variables);
  const result = parser.parseExpression();
  if (!Number.isFinite(result)) throw new Error('Kết quả không hợp lệ');
  return result;
}

export function trySafeEval(expr: string, variables: Record<string, number> = {}): number | null {
  try {
    return safeEvalExpression(expr, variables);
  } catch {
    return null;
  }
}
