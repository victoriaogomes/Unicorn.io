import abc


class Expr:
    @abc.abstractmethod
    def accept(self, visitor):
        raise NotImplementedError


class Assign(Expr):
    # Assign: token = expr;
    def __init__(self, token, expr, scope):
        self.token = token
        self.expr = expr
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitAssignExpr(self)


class Binary(Expr):
    # 5 + 4
    def __init__(self, left_expr, token_operator, right_expr, scope):
        self.left_expr = left_expr
        self.token_operator = token_operator
        self.right_expr = right_expr
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitBinaryExpr(self)


class FunctionCall(Expr):
    # ano();
    def __init__(self, arguments, func_exp, token_parenthesis, scope):
        self.arguments = arguments
        self.func_exp = func_exp
        self.token_parenthesis = token_parenthesis
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitFCallExpr(self)


class StructGet(Expr):
    # Pessoa.nome
    def __init__(self, struct_name, attr_name, scope):
        self.struct_name = struct_name
        self.attr_name = attr_name
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitStructGetExpr(self)


class StructSet(Expr):
    # Pessoa.nome = Bruno
    def __init__(self, struct_name, attr_name, expr_value, scope):
        self.struct_name = struct_name
        self.attr_name = attr_name
        self.expr_value = expr_value
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitStructSetExpr(self)


class Grouping(Expr):
    # (expr)
    def __init__(self, expr, scope):
        self.expr = expr
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitGroupingExpr(self)


class LiteralVal(Expr):
    # int, real, string, boolean, IDE
    def __init__(self, value, scope):
        self.value = value
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitLitValExpr(self)


class Logical(Expr):
    # &&, ||
    def __init__(self, left_expr, token_operator, right_expr, scope):
        self.left_expr = left_expr
        self.token_operator = token_operator
        self.right_expr = right_expr
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitLogicalExpr(self)


class Unary(Expr):
    # !b, -5
    def __init__(self, token_operator, right_expr, scope):
        self.token_operator = token_operator
        self.right_expr = right_expr
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitUnaryExpr(self)


class ConstVarAccess(Expr):
    # nome, idade
    def __init__(self, token_name, scope, access_type='local', index_array=-1, index_matrix=-1):
        self.token_name = token_name
        self.access_type = access_type
        self.index_array = index_array
        self.index_matrix = index_matrix
        self.scope = scope

    def accept(self, visitor):
        return visitor.visitConstVarAccessExpr(self)
