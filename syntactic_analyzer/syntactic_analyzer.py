from syntactic_analyzer import firsts_follows as f
import inspect
from copy import deepcopy
from syntactic_analyzer import symbol_table as s
from semantic_analyzer import expressions as expr, statements as stmt
from lexical_analyzer import tokens as tk


class SyntacticAnalyzer:

    def __init__(self, tokens_list):
        self.tokens_list = tokens_list
        self.output_list = deepcopy(tokens_list)
        self.global_table = s.SymbolTable(None)
        self.Line = s.TableLine('', '', '', [], 0, [])
        self.scope_index = -1
        self.global_scope = True
        self.error = False
        self.program = []
        self.stmt_var_block = stmt.Var_block([], None)
        self.stmt_const_block = stmt.Const_block([], None)
        self.st_var = stmt.Var(None, None, None, None, None)
        self.struct = stmt.Struct(None, [], None)
        self.func_stmt = stmt.Function(None, None, None, None, None, None)
        self.proc_stmt = stmt.Procedure(None, None, None, None)

    def add_new_symb_table(self, f_line):
        self.scope_index += 1
        aux = s.SymbolTable(self.global_table)
        aux.set_line(f_line)
        self.global_table.add_child(aux)

    def add_line_on_table(self, reset_type):
        if not self.global_scope:
            self.global_table.children[self.scope_index].add_line(deepcopy(self.Line))
        else:
            self.global_table.add_line(deepcopy(self.Line))
        self.Line.reset_for(reset_type)

# =====================================================================================================================
# ==================================================== Code Scope =====================================================

    # Estado inicial da gramática, define possíveis formas de iniciar o código (um ou nenhum bloco var, um ou nenhum
    # bloco const, nenhum ou vários typedef, nenhum ou várias structs, nenhum ou várias funções e procedures, um único
    # procedure start)
    def start(self):
        if self.tokens_list.lookahead().lexeme == 'typedef':
            self.program.append(self.typedef_declaration())
            self.start()
        elif self.tokens_list.lookahead().lexeme == 'struct':
            self.program.append(self.structure_declaration())
            self.start()
        elif self.tokens_list.lookahead().lexeme == 'var':
            self.program.append(self.var_declaration())
            self.header1()
        elif self.tokens_list.lookahead().lexeme == 'const':
            self.program.append(self.const_declaration())
            self.header2()
        elif self.tokens_list.lookahead().lexeme in {'function', 'procedure'}:
            self.methods()
            # self.program.extend(self.methods())
        else:
            self.error_treatment('START', 'typedef ou struct ou var ou const ou function ou procedure')
        return self.program

    # Estado chamado caso o usuário declare um bloco var, para que não seja possível adicionar outro bloco desse tipo
    # fora de uma function ou procedure
    def header1(self):
        if self.tokens_list.lookahead().lexeme == 'typedef':
            self.program.append(self.typedef_declaration())
            self.header1()
        elif self.tokens_list.lookahead().lexeme == 'struct':
            self.program.append(self.structure_declaration())
            self.header1()
        elif self.tokens_list.lookahead().lexeme == 'const':
            self.program.append(self.const_declaration())
            self.header3()
        elif self.tokens_list.lookahead().lexeme in {'function', 'procedure'}:
            self.methods()
        else:
            self.error_treatment('HEADER1', 'typedef ou struct ou const ou function ou procedure')

    # Estado chamado caso o usuário declare um bloco const, para que não seja possível adicionar outro bloco desse tipo
    # fora de uma function ou procedure
    def header2(self):
        if self.tokens_list.lookahead().lexeme == 'typedef':
            self.program.append(self.typedef_declaration())
            self.header2()
        elif self.tokens_list.lookahead().lexeme == 'struct':
            self.program.append(self.structure_declaration())
            self.header2()
        elif self.tokens_list.lookahead().lexeme == 'var':
            self.program.append(self.var_declaration())
            self.header3()
        elif self.tokens_list.lookahead().lexeme in {'function', 'procedure'}:
            self.methods()
        else:
            self.error_treatment('HEADER2', 'typedef ou struct ou var ou function ou procedure')

    # Estado chamado caso o usuário declare um bloco var e um bloco const, para que não seja possível adicionar outros
    # blocos desse tipo fora de uma function ou procedure
    def header3(self):
        if self.tokens_list.lookahead().lexeme == 'typedef':
            self.program.append(self.typedef_declaration())
            self.header3()
        elif self.tokens_list.lookahead().lexeme == 'struct':
            self.program.append(self.structure_declaration())
            self.header3()
        elif self.tokens_list.lookahead().lexeme in {'function', 'procedure'}:
            self.methods()
        else:
            self.error_treatment('HEADER3', 'typedef ou struct ou function ou procedure')

    # Loop que permite adicionar funções e procedures antes do procedure start, e obriga a ter um único procedure start
    # no fim de todos os códigos
    def methods(self):
        if self.tokens_list.lookahead().lexeme == 'function':
            self.program.append(self.function())
            self.methods()
        elif self.tokens_list.lookahead().lexeme == 'procedure':
            self.Line.program_line = self.tokens_list.lookahead().file_line
            self.tokens_list.consume_token()
            self.Line.tp = 'procedure'
            self.proc_choice()
        else:
            self.error_treatment('METHODS', 'function ou procedure')

    # Estado para escolher entre a declaração de um procedure qualquer ou um procedure start
    def proc_choice(self):
        self.proc_stmt = stmt.Procedure(self.tokens_list.lookahead(), None, [], None)
        if self.tokens_list.lookahead().lexeme == 'start':
            self.tokens_list.consume_token()
            self.Line.name = 'start'
            self.start_procedure()
            self.program.append(self.proc_stmt)
            if self.tokens_list.lookahead().lexeme != 'endOfFile($)':
                self.output_list.add_token('ERRO SINTATICO: NESSA LINGUAGEM, ESPERA-SE QUE'
                                           + ' O ARQUIVO FINALIZE APOS O PROCEDURE START. CODIGOS'
                                           + ' APOS O PROCEDURE START NAO SAO ANALISADOS SINTATICAMENTE', '',
                                           self.tokens_list.lookahead().file_line)
                self.error = True
        elif self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.procedure()
            self.program.append(self.proc_stmt)
            self.methods()
        else:
            self.error_treatment('PROCCHOICE', 'start ou Identificador')

# =====================================================================================================================
# ====================================================== Data Types ===================================================

    # Estado que possui as maneiras possíveis de acessar uma variável (usando os modificadores global e local ou não)
    def variable(self):
        if self.tokens_list.lookahead().lexeme_type == 'IDE':
            name = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            aux = self.cont_element()
            if isinstance(aux, expr.ConstVarAccess):
                aux.token_name = name
            elif isinstance(aux, expr.StructGet):
                aux.struct_name = expr.ConstVarAccess(name, self.get_scope())
            elif aux is None:
                aux = expr.ConstVarAccess(name, self.get_scope())
            return aux
        elif self.tokens_list.lookahead().lexeme in {'global', 'local'}:
            return self.scope_variable()
        else:
            self.error_treatment('VARIABLE', 'Identificador ou global ou local')
        return None

    # Estado que possui as maneiras possíveis de acessar uma variável usando os modificadores global e local
    def scope_variable(self):
        if self.tokens_list.lookahead().lexeme in {'global', 'local'}:
            tp_access = self.tokens_list.lookahead().lexeme
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '.':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme_type == 'IDE':
                    name = self.tokens_list.lookahead()
                    self.tokens_list.consume_token()
                    aux = self.cont_element()
                    if isinstance(aux, expr.ConstVarAccess):
                        aux.token_name = name
                        aux.access_type = tp_access
                    elif isinstance(aux, expr.StructGet):
                        aux.struct_name = expr.ConstVarAccess(name, self.get_scope(), tp_access)
                    elif aux is None:
                        aux = expr.ConstVarAccess(name, self.get_scope(), tp_access)
                    return aux
                else:
                    self.error_treatment('SCOPEVARIABLE', 'Identificador')
            else:
                self.error_treatment('SCOPEVARIABLE', '.')
        else:
            self.error_treatment('SCOPEVARIABLE', 'global ou local')
        return None

    # Valores que podem ser utilizados para indexar um vetor
    def vect_mat_index(self):
        if self.tokens_list.lookahead().lexeme in {'true', 'false', 'global', 'local', '('}:
            return self.arit_exp1()
        elif self.tokens_list.lookahead().lexeme_type in {'NRO', 'IDE', 'CAD'}:
            return self.arit_exp1()
        else:
            self.error_treatment('VECTMATINDEX',
                                 'true ou false ou global ou local ou ( ou Numero ou Identificador ou Cadeida de '
                                 'caracteres')
        return None

    # Tipos de dados que podem ser usados ao declarar uma função, uma variável ou uma constante. Identificador está
    # incluído, pois o typedef pode ter sido usado para definir um novo tipo
    def data_type(self):
        if self.tokens_list.lookahead().lexeme in {'int', 'string', 'real', 'boolean'}:
            if self.Line.tp not in {'function', 'procedure', 'struct'} or \
                    (self.Line.data_type == '' and self.Line.tp == 'function'):
                self.Line.data_type = self.tokens_list.lookahead().lexeme
            self.tokens_list.consume_token()
        elif self.tokens_list.lookahead().lexeme_type == 'IDE':
            if self.Line.tp not in {'function', 'procedure', 'struct'} or \
                    (self.Line.data_type == '' and self.Line.tp == 'function'):
                if self.Line.data_type != '':
                    self.Line.data_type = self.Line.data_type + '.' + self.tokens_list.lookahead().lexeme
                else:
                    self.Line.data_type = self.tokens_list.lookahead().lexeme
            self.tokens_list.consume_token()
        else:
            self.error_treatment('DATATYPE', 'int ou string ou real ou boolean ou Identificador')

    # Estado para a escolha do elemento a ser acessado (struct, vetor ou matriz)
    def cont_element(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            a_index = self.vect_mat_index()
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                matrix = self.matrix_e1()
                if matrix is None:
                    return expr.ConstVarAccess(None, self.get_scope(), index_array=a_index)
                elif isinstance(matrix, expr.StructGet):
                    if matrix.struct_name is None:
                        matrix.struct_name = expr.ConstVarAccess(None, self.get_scope(), index_array=a_index)
                    else:
                        matrix.struct_name.index_array = a_index
                    return matrix
                elif isinstance(matrix, expr.ConstVarAccess):
                    matrix.index_array = a_index
                    return matrix
            else:
                self.error_treatment('CONTELEMENT', ']')
        else:
            return self.matrix_e2()
        return None

    # Um dos estados usados para tornar possível o acesso a vetor, matriz, struct, matriz dentro de struct, e matriz de
    # struct
    def struct_e1(self):
        if self.tokens_list.lookahead().lexeme == '.':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                attr_name = self.tokens_list.lookahead()
                self.tokens_list.consume_token()
                aux = self.cont_element()
                if aux is None:
                    return expr.StructGet(None, expr.ConstVarAccess(attr_name, self.get_scope()), self.get_scope())
                elif isinstance(aux, expr.StructGet):
                    aux.struct_name = expr.ConstVarAccess(attr_name, self.get_scope())
                    return expr.StructGet(None, aux, self.get_scope())
                elif isinstance(aux, expr.ConstVarAccess):
                    aux.token_name = attr_name
                    return expr.StructGet(None, aux, self.get_scope())
            else:
                self.error_treatment('STRUCTE1', 'Identificador')
        else:
            self.error_treatment('STRUCTE1', '.')
        return None

    # Um dos estados usados para tornar possível o acesso a vetor, matriz, struct, matriz dentro de struct, e matriz de
    # struct
    def matrix_e1(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            m_index = self.vect_mat_index()
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                access = self.matrix_e2()
                if access is None:
                    return expr.ConstVarAccess(None, self.get_scope(), index_matrix=m_index)
                elif isinstance(access, expr.StructGet):
                    access.struct_name = expr.ConstVarAccess(None, self.get_scope(), index_matrix=m_index)
                    return access
            else:
                self.error_treatment('MATRIZE1', ']')
        else:
            return self.matrix_e2()
        return None

    # Um dos estados usados para tornar possível o acesso a vetor, matriz, struct, matriz dentro de struct, e matriz de
    # struct
    def matrix_e2(self):
        if self.tokens_list.lookahead().lexeme == '.':
            return self.struct_e1()
        return None

# =====================================================================================================================
# ================================================ Variable Declaration ===============================================

    # Estado responsável pela declaração de um bloco var
    def var_declaration(self):
        self.stmt_var_block = stmt.Var_block([], self.get_scope())
        if self.tokens_list.lookahead().lexeme == 'var':
            self.tokens_list.consume_token()
            self.Line.tp = 'var'
            if self.tokens_list.lookahead().lexeme == '{':
                self.tokens_list.consume_token()
                self.first_var()
            else:
                self.error_treatment('VARDECLARATION', '{')
        else:
            self.error_treatment('VARDECLARATION', 'var')
        return self.stmt_var_block

    # Estado chamado uma única vez, para garantir que no mínimo uma variável será declarada no bloco var
    def first_var(self):
        if self.tokens_list.lookahead().lexeme in {'int', 'real', 'boolean', 'struct', 'string'}:
            self.continue_sos()
            self.var_id()
        elif self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.continue_sos()
            self.var_id()
        else:
            self.error_treatment('FIRSTVAR', 'int ou real ou boolean ou struct ou Identificador')

    # Estado chamado a partir da segunda declaração de variável, para que seja finalizada a declaração, ou que outras
    # variáveis do mesmo tipo sejam enumeradas na mesma linha
    def next_var(self):
        if self.tokens_list.lookahead().lexeme in {'int', 'real', 'boolean', 'struct', 'string'}:
            self.continue_sos()
            self.var_id()
        elif self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.continue_sos()
            self.var_id()
        elif self.tokens_list.lookahead().lexeme == '}':
            self.tokens_list.consume_token()
            self.Line.reset_for(0)
        else:
            self.error_treatment('NEXTVAR', 'int ou real ou boolean ou struct ou string ou Identificador ou }')

    # Estado que define o tipo de variável que está sendo declarada (struct ou demais tipos)
    def continue_sos(self):
        self.Line.program_line = self.tokens_list.lookahead().file_line
        if self.tokens_list.lookahead().lexeme == 'struct':
            self.tokens_list.consume_token()
            self.Line.data_type = 'struct'
            self.data_type()
        else:
            self.data_type()

    # Estado que define o identificador da variável que está sendo declarada
    def var_id(self):
        if self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.Line.name = self.tokens_list.lookahead().lexeme
            self.tokens_list.consume_token()
            self.var_exp()
        else:
            self.error_treatment('VARID', 'Identificador')

    # Expressão que pode vir após uma variável: uma vírgula, para declarar outras variáveis do mesmo tipo; uma
    # incialização de variável; um ponto e vírgula, para fechar as declarações desse tipo; um abre colchetes, para
    # declaração de vetor
    def var_exp(self):
        if self.tokens_list.lookahead().lexeme == ',':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line)
            self.stmt_var_block.var_list.append(nvar)
            self.add_line_on_table(1)
            self.tokens_list.consume_token()
            self.var_id()
        elif self.tokens_list.lookahead().lexeme == '=':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.verif_var()
        elif self.tokens_list.lookahead().lexeme == ';':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line)
            self.stmt_var_block.var_list.append(nvar)
            self.add_line_on_table(2)
            self.tokens_list.consume_token()
            self.next_var()
        elif self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            aux = self.vect_mat_index()
            self.Line.indexes[0] = aux
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                self.structure()
            else:
                self.error_treatment('VAREXP', ']')
        else:
            self.error_treatment('VAREXP', ', ou = ou ; ou [')

    # Expressões possíveis após um vetor: uma vírgula, para declarar outras variáveis do mesmo tipo; uma
    # incialização de variável; um ponto e vírgula, para fechar as declarações desse tipo; um abre colchetes, para
    # declarar uma matriz
    def structure(self):
        if self.tokens_list.lookahead().lexeme == ',':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line)
            self.stmt_var_block.var_list.append(nvar)
            self.add_line_on_table(1)
            self.tokens_list.consume_token()
            self.var_id()
        elif self.tokens_list.lookahead().lexeme == '=':
            self.tokens_list.consume_token()
            self.init_array()
        elif self.tokens_list.lookahead().lexeme == ';':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line)
            self.stmt_var_block.var_list.append(nvar)
            self.tokens_list.consume_token()
            self.add_line_on_table(2)
            self.next_var()
        elif self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            aux = self.vect_mat_index()
            self.Line.indexes[1] = aux
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                self.cont_matrix()
            else:
                self.error_treatment('STRUCTURE', ']')
        else:
            self.error_treatment('STRUCTURE', ', ou = ou ; ou {')

    # Expressões possíveis após uma matriz: uma vírgula, para declarar outras variáveis do mesmo tipo; uma
    # incialização de variável e um ponto e vírgula, para fechar as declarações desse tipo
    def cont_matrix(self):
        if self.tokens_list.lookahead().lexeme == '=':
            self.tokens_list.consume_token()
            self.init_matrix()
        elif self.tokens_list.lookahead().lexeme == ',':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line, self.Line.indexes[0],
                            self.Line.indexes[1])
            self.stmt_var_block.var_list.append(nvar)
            self.tokens_list.consume_token()
            self.add_line_on_table(1)
            self.var_id()
        elif self.tokens_list.lookahead().lexeme == ';':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line,self.Line.indexes[0],
                            self.Line.indexes[1])
            self.stmt_var_block.var_list.append(nvar)
            self.add_line_on_table(2)
            self.tokens_list.consume_token()
            self.next_var()
        else:
            self.error_treatment('CONTMATRIX', '= ou , ou ;')

    # Estado responsável pela inicialização de um vetor
    def init_array(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            self.Line.value
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.next_array()
        else:
            self.error_treatment('INITARRAY', '[')

    # Estado para auxiliar a inicialização de um vetor
    def next_array(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.next_array()
        elif self.tokens_list.lookahead().lexeme == ']':
            self.tokens_list.consume_token()
            self.verif_var()
        else:
            self.error_treatment('NEXTARRAY', ', ou ]')

    # Estado responsável pela inicialização de uma matriz
    def init_matrix(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            self.matrix_value()
        else:
            self.error_treatment('INITMATRIX', '[')

    # Estado para auxiliar a inicialização de uma matriz
    def matrix_value(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.next_matrix()
        else:
            self.error_treatment('MATRIXVALUE', '[')

    # Estado para auxiliar a inicialização de uma matriz
    def next_matrix(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.next_matrix()
        elif self.tokens_list.lookahead().lexeme == ']':
            self.tokens_list.consume_token()
            self.next()
        else:
            self.error_treatment('NEXTVALUE', ', ou ]')

    # Estado para auxiliar a inicialização de uma matriz
    def next(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            self.matrix_value()
        elif self.tokens_list.lookahead().lexeme == ']':
            self.tokens_list.consume_token()
            self.verif_var()
        else:
            self.error_treatment('NEXT', ', ou ]')

    # Estado utilizado para verificar se a declaração de variáveis de um mesmo tipo deve ser finalizada ou não
    def verif_var(self):
        if self.tokens_list.lookahead().lexeme == ',':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line, self.Line.indexes[0],
                            self.Line.indexes[1])
            self.stmt_var_block.var_list.append(nvar)
            self.tokens_list.consume_token()
            self.add_line_on_table(1)
            self.var_id()
        elif self.tokens_list.lookahead().lexeme == ';':
            nvar = stmt.Var(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line, self.Line.indexes[0],
                            self.Line.indexes[1])
            self.stmt_var_block.var_list.append(nvar)
            self.tokens_list.consume_token()
            self.add_line_on_table(2)
            self.next_var()
        else:
            self.error_treatment('VERIFVAR', ', ou ;')

# =====================================================================================================================
# =============================================== Const Declaration ===================================================

    # Estado responsável pela declaração de um bloco const
    def const_declaration(self):
        self.stmt_const_block = stmt.Const_block([], self.get_scope())
        if self.tokens_list.lookahead().lexeme == 'const':
            self.tokens_list.consume_token()
            self.Line.tp = 'const'
            if self.tokens_list.lookahead().lexeme == '{':
                self.tokens_list.consume_token()
                self.first_const()
            else:
                self.error_treatment('CONSTDECLARATION', '{')
        else:
            self.error_treatment('CONSTDECLARATION', 'const')
        return self.stmt_const_block

    # Estado chamado uma única vez, para garantir que no mínimo uma variável será declarada no bloco const
    def first_const(self):
        self.continue_const_sos()
        self.const_id()

    # Estado que define o tipo de constante que está sendo declarada (struct ou demais tipos)
    def continue_const_sos(self):
        self.Line.program_line = self.tokens_list.lookahead().file_line
        if self.tokens_list.lookahead().lexeme == 'struct':
            self.tokens_list.consume_token()
            self.Line.data_type = 'struct'
            self.data_type()
        else:
            self.data_type()

    # Estado chamado a partir da segunda declaração de constante, para que seja finalizada a declaração, ou que outras
    # constantes do mesmo tipo sejam enumeradas na mesma linha
    def next_const(self):
        if self.tokens_list.lookahead().lexeme == '}':
            self.tokens_list.consume_token()
            self.Line.reset_for(0)
        else:
            self.continue_const_sos()
            self.const_id()

    # Estado que define o identificador da constante que está sendo declarada
    def const_id(self):
        if self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.Line.name = self.tokens_list.lookahead().lexeme
            self.tokens_list.consume_token()
            self.const_exp()
        else:
            self.error_treatment('CONSTID', 'Identificador')

    # Expressão que pode vir após uma variável:uma incialização de constante ou um abre colchetes, para declaração de
    # vetor
    def const_exp(self):
        if self.tokens_list.lookahead().lexeme == '=':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.verif_const()
        elif self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            aux = self.vect_mat_index()
            self.Line.indexes[0] = aux
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                self.const_structure()
            else:
                self.error_treatment('CONSTEXP', ']')

    # Expressões possíveis após um vetor: inicialização do vetor ou colchetes para declarar matriz
    def const_structure(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            aux = self.vect_mat_index()
            self.Line.indexes[1] = aux
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '=':
                    self.tokens_list.consume_token()
                    self.init_const_matrix()
                else:
                    self.error_treatment('CONSTSTRUCTURE', '=')
            else:
                self.error_treatment('CONSTSTRUCTURE', ']')
        elif self.tokens_list.lookahead().lexeme == '=':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '[':
                self.tokens_list.consume_token()
                expr1 = self.expression()
                self.Line.value.append(expr1)
                self.next_const_array()
            else:
                self.error_treatment('CONSTSTRUCTURE', '[')
        else:
            self.error_treatment('CONSTSTRUCTURE', '] ou =')

    # Estado responsável pela inicialização de um vetor
    def next_const_array(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.next_const_array()
        elif self.tokens_list.lookahead().lexeme == ']':
            self.tokens_list.consume_token()
            self.verif_const()
        else:
            self.error_treatment('NEXTCONSTARRAY', ', ou ]')

    # Estado responsáveL pela inicialização de uma matriz
    def init_const_matrix(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            self.matrix_const_value()
        else:
            self.error_treatment('INITCONSTMATRIX', '[')

    # Estado para auxiliar a inicialização de uma matriz
    def matrix_const_value(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.next_const_matrix()
        else:
            self.error_treatment('MATRIXCONSTVALUE', '[')

    # Estado para auxiliar a inicialização de uma matriz
    def next_const_matrix(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            self.Line.value.append(expr1)
            self.next_const_matrix()
        elif self.tokens_list.lookahead().lexeme == ']':
            self.tokens_list.consume_token()
            self.next_const2()
        else:
            self.error_treatment('NEXTCONSTMATRIX', ', ou ]')

    # Estado para auxiliar a inicialização de uma matriz
    def next_const2(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            self.matrix_const_value()
        elif self.tokens_list.lookahead().lexeme == ']':
            self.tokens_list.consume_token()
            self.verif_const()
        else:
            self.error_treatment('NEXTCONST2', ', ou ]')

    # Estado utilizado para verificar se a declaração de constantes de um mesmo tipo deve ser finalizada ou não
    def verif_const(self):
        if self.tokens_list.lookahead().lexeme == ',':
            nconst = stmt.Const(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line,
                                self.Line.indexes[0], self.Line.indexes[1])
            self.stmt_const_block.const_list.append(nconst)
            self.tokens_list.consume_token()
            self.add_line_on_table(1)
            self.const_id()
        elif self.tokens_list.lookahead().lexeme == ';':
            nconst = stmt.Const(self.Line.name, self.Line.value, self.Line.data_type, self.get_scope(), self.Line.program_line,
                                self.Line.indexes[0], self.Line.indexes[1])
            self.stmt_const_block.const_list.append(nconst)
            self.tokens_list.consume_token()
            self.add_line_on_table(2)
            self.next_const()
        else:
            self.error_treatment('VERIFCONST', ', ou ;')

# =====================================================================================================================
# =============================================== Function Statement ==================================================

    # Estado utilizado para a criação de uma nova função
    def function(self):
        self.func_stmt = stmt.Function(None, [], [], None, None, None)
        if self.tokens_list.lookahead().lexeme == 'function':
            self.Line.program_line = self.tokens_list.lookahead().file_line
            self.tokens_list.consume_token()
            self.Line.tp = 'function'
            self.func_stmt.return_tp = self.tokens_list.lookahead()
            self.data_type()
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                self.func_stmt.token_name = self.tokens_list.lookahead()
                self.Line.name = self.tokens_list.lookahead().lexeme
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '(':
                    self.tokens_list.consume_token()
                    self.continue_function()
                else:
                    self.error_treatment('FUNCTION', '(')
            else:
                self.error_treatment('FUNCTION', 'Identificador')
        else:
            self.error_treatment('FUNCTION', 'function')
        return self.func_stmt

    # Estado que permite que, caso o usuário deseje, sejam definidos parâmetros para essa função
    def continue_function(self):
        if self.tokens_list.lookahead().lexeme == ')':
            self.tokens_list.consume_token()
            self.block_function()
        elif self.tokens_list.lookahead().lexeme in {'int', 'real', 'string', 'boolean', 'struct'}:
            self.parameters()
            self.block_function()
        elif self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.parameters()
            self.block_function()
        else:
            self.error_treatment('CONTINUEFUNCTION', ') ou int ou real ou string ou boolean ou struct ou Identificador')

    # Estado para adicionar parâmetros a função
    def parameters(self):
        if self.tokens_list.lookahead().lexeme in {'int', 'real', 'string',
                                                   'boolean'} or self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.Line.params.append(self.tokens_list.lookahead().lexeme)
            self.data_type()
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                self.Line.params[-1] += '.' + self.tokens_list.lookahead().lexeme
                self.tokens_list.consume_token()
                self.param_loop()
            else:
                self.error_treatment('PARAMETERS', 'Identificador')
        elif self.tokens_list.lookahead().lexeme == 'struct':
            self.Line.params.append('struct')
            self.tokens_list.consume_token()
            self.Line.params[-1] += '.' + self.tokens_list.lookahead().lexeme
            self.data_type()
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                self.Line.params[-1] += '.' + self.tokens_list.lookahead().lexeme
                self.tokens_list.consume_token()
                self.param_loop()
            else:
                self.error_treatment('PARAMETERS', 'Identificador')
        else:
            self.error_treatment('PARAMETERS', 'int ou real ou string ou boolean ou Identificador ou struct')

    # Estado que realiza o loop para a adição de um ou mais parâmetros a função
    def param_loop(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            self.parameters()
        elif self.tokens_list.lookahead().lexeme == ')':
            self.tokens_list.consume_token()
        else:
            self.error_treatment('PARAMLOOP', ', ou )')

    # Definição do bloco da função
    def block_function(self):
        if self.tokens_list.lookahead().lexeme == '{':
            self.tokens_list.consume_token()
            self.func_stmt.params = self.Line.params
            aux = deepcopy(self.Line)
            self.add_line_on_table(0)
            self.add_new_symb_table(aux)
            self.global_scope = False
            self.func_stmt.scope = self.get_scope()
            self.block_function_content()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '}':
                    self.tokens_list.consume_token()
                    self.global_scope = True
                else:
                    self.error_treatment('BLOCKFUNCTION', '}')
            else:
                self.error_treatment('BLOCKFUNCTION', ';')
        else:
            self.error_treatment('BLOCKFUNCTION', '{')

    # Definição do conteúdo interno do bloco da função: permite uma ou nenhuma declaração de constante e variável antes
    # das demais linhas de código
    def block_function_content(self):
        if self.tokens_list.lookahead().lexeme == 'var':
            self.func_stmt.body.append(self.var_declaration())
            self.content1()
        elif self.tokens_list.lookahead().lexeme == 'const':
            self.func_stmt.body.append(self.const_declaration())
            self.content2()
        else:
            self.function_content()

    # Código interno de uma função, seguido do retorno obrigatório
    def function_content(self):
        var_code = self.code()
        if var_code is not None:
            self.func_stmt.body.extend(var_code)
        if self.tokens_list.lookahead().lexeme == 'return':
            self.func_stmt.return_expr = stmt.Returnf(self.tokens_list.lookahead(), None, self.get_scope())
            self.tokens_list.consume_token()
            self.func_stmt.return_expr.value = self.expression()
        else:
            self.error_treatment('FUNCTIONCONTENT', 'return')

    # Estado que permite apenas declaração de constante, assumindo que um bloco var foi declarado anteriormente
    def content1(self):
        if self.tokens_list.lookahead().lexeme == 'const':
            self.func_stmt.body.append(self.const_declaration())
            self.content3()
        else:
            self.function_content()

    # Estado que permite apenas declaração de variável, assumindo que um bloco const foi declarado anteriormente
    def content2(self):
        if self.tokens_list.lookahead().lexeme == 'var':
            self.func_stmt.body.append(self.var_declaration())
            self.content3()
        else:
            self.function_content()

    # Estado que redireciona diretamente para função que não possui declarações de var e const
    def content3(self):
        self.function_content()

# =====================================================================================================================
# =============================================== Struct Declaration ==================================================

    # Declaração de um elemento do tipo struct
    def structure_declaration(self):
        self.struct = stmt.Struct(None, [], self.get_scope())
        if self.tokens_list.lookahead().lexeme == 'struct':
            self.Line.program_line = self.tokens_list.lookahead().file_line
            self.tokens_list.consume_token()
            self.Line.tp = 'struct'
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                name = self.tokens_list.lookahead()
                self.struct.name = name
                self.Line.name = self.tokens_list.lookahead().lexeme
                self.tokens_list.consume_token()
                self.struct_vars()
            else:
                self.error_treatment('STRUCTUREDECLARATION', 'Identificador')
        else:
            self.error_treatment('STRUCTUREDECLARATION', 'struct')
        return self.struct

    # Declaração do bloco var contido dentro da struct que está sendo definida (blocos const não são permitidos) ou
    # definição da herança de variáveis de uma struct definida anteriormente
    def struct_vars(self):
        if self.tokens_list.lookahead().lexeme == '{':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == 'var':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    self.first_struct_var()
                else:
                    self.error_treatment('STRUCTVARS', '{')
            else:
                self.error_treatment('STRUCTVARS', 'var')
        elif self.tokens_list.lookahead().lexeme == 'extends':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                self.struct.extends = self.tokens_list.lookahead()
                self.Line.data_type = self.tokens_list.lookahead().lexeme
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    if self.tokens_list.lookahead().lexeme == 'var':
                        self.tokens_list.consume_token()
                        if self.tokens_list.lookahead().lexeme == '{':
                            self.tokens_list.consume_token()
                            self.first_struct_var()
                        else:
                            self.error_treatment('STRUCTVARS', '{')
                    else:
                        self.error_treatment('STRUCTVARS', 'var')
                else:
                    self.error_treatment('STRUCTVARS', '{')
            else:
                self.error_treatment('STRUCTVARS', 'Identificador')
        else:
            self.error_treatment('STRUCTVARS', '{ ou extends')

    # Declaração da primeira variável da struct, pois é necessária no mínimo uma
    def first_struct_var(self):
        self.Line.params.append(self.tokens_list.lookahead().lexeme)
        self.st_var.tp = self.tokens_list.lookahead().lexeme
        self.data_type()
        self.struct_var_id()

    # Declaração do id da variável da struct
    def struct_var_id(self):
        if self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.st_var.name = self.tokens_list.lookahead()
            self.Line.params[-1] += '.' + self.tokens_list.lookahead().lexeme
            self.tokens_list.consume_token()
            self.struct_var_exp()
        else:
            self.error_treatment('STRUCTVARID', 'Identificador')

    # Estado utilizado para declarar variáveis, a partir da segunda
    def next_struct_var(self):
        if self.tokens_list.lookahead().lexeme == '}':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
                self.add_line_on_table(0)
            else:
                self.error_treatment('NEXTSTRUCTVAR', '}')
        elif self.tokens_list.lookahead().lexeme_type == 'IDE' or \
                self.tokens_list.lookahead().lexeme in {'int', 'real', 'string', 'boolean'}:
            self.Line.params.append(self.tokens_list.lookahead().lexeme)
            self.st_var.tp = self.tokens_list.lookahead().lexeme
            self.data_type()
            self.struct_var_id()
        else:
            self.error_treatment('NEXTSTRUCTVAR', '} ou Identificador ou int ou real ou string ou boolean')

    # Expressões possíveis após uma variável: colocar uma vírgula e enumerar outras variáveis, finalizar a declaração
    # desse tipo de variável ou iniciar a declaração de um vetor
    def struct_var_exp(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.struct.variables.append(deepcopy(self.st_var))
            self.st_var = stmt.Var(None, None, self.st_var.tp, self.get_scope(), self.Line.program_line)
            self.Line.params.append(self.Line.params[-1].split(sep='.')[0])
            self.tokens_list.consume_token()
            self.struct_var_id()
        elif self.tokens_list.lookahead().lexeme == ';':
            self.struct.variables.append(deepcopy(self.st_var))
            self.st_var = stmt.Var(None, None, None, self.get_scope(), self.Line.program_line)
            self.tokens_list.consume_token()
            self.next_struct_var()
        elif self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            self.tokens_list.math_mode_switch()
            self.st_var.index_array = self.vect_mat_index()
            self.Line.params[-1] += '.' + self.tokens_list.expression
            self.tokens_list.math_mode_switch()
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                self.struct_matrix()
            else:
                self.error_treatment('STRUCTVAREXP', '}')
        else:
            self.error_treatment('STRUCTVAREXP', ', ou ; ou [')

    # Estado responsável pela declaração de matriz dentro do bloco var da struct
    def struct_matrix(self):
        if self.tokens_list.lookahead().lexeme == '[':
            self.tokens_list.consume_token()
            self.tokens_list.math_mode_switch()
            self.st_var.index_matrix = self.vect_mat_index()
            self.Line.params[-1] = '.' + self.tokens_list.expression
            self.tokens_list.math_mode_switch()
            if self.tokens_list.lookahead().lexeme == ']':
                self.tokens_list.consume_token()
                self.cont_struct_matrix()
            else:
                self.error_treatment('STRUCTMATRIX', ']')
        elif self.tokens_list.lookahead().lexeme == ',':
            self.struct.variables.append(deepcopy(self.st_var))
            self.st_var = stmt.Var(None, None, self.st_var.tp, self.get_scope(), self.Line.program_line)
            self.tokens_list.consume_token()
            self.Line.params.append(self.Line.params[-1].split(sep='.')[0])
            self.struct_var_id()
        elif self.tokens_list.lookahead().lexeme == ';':
            self.struct.variables.append(deepcopy(self.st_var))
            self.st_var = stmt.Var(None, None, None, self.get_scope(), self.Line.program_line)
            self.tokens_list.consume_token()
            self.next_struct_var()
        else:
            self.error_treatment('STRUCTMATRIX', '[ ou , ou ;')

    # Estado para auxiliar a declaração de matriz dentro do bloco var da struct
    def cont_struct_matrix(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.struct.variables.append(deepcopy(self.st_var))
            self.st_var = stmt.Var(None, None, self.st_var.tp, self.get_scope(), self.Line.program_line)
            self.Line.params.append(self.Line.params[-1].split(sep='.')[0])
            self.tokens_list.consume_token()
            self.struct_var_id()
        elif self.tokens_list.lookahead().lexeme == ';':
            self.struct.variables.append(deepcopy(self.st_var))
            self.st_var = stmt.Var(None, None, None, self.get_scope(), self.Line.program_line)
            self.tokens_list.consume_token()
            self.next_struct_var()
        else:
            self.error_treatment('CONTSTRUCTMATRIX', ', ou ;')

# =====================================================================================================================
# ================================================== Operations =======================================================

    # Estado que inicia a declaração de uma expressão, que poderá ser lógica, relacional ou aritmética
    def expression(self):
        if self.tokens_list.lookahead().lexeme in {'!', '-'}:
            exc = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            expr1 = self.rel_exp()
            expr2 = self.log_exp()
            if expr2 is None:
                return expr.Unary(exc, expr1, self.get_scope())
            else:
                expr2.left_expr = expr1
                return expr.Unary(exc, expr2, self.get_scope())
        elif self.tokens_list.lookahead().lexeme in {'true', 'false', 'global', 'local', '('}:
            expr1 = self.rel_exp()
            expr2 = self.log_exp()
            if expr2 is None:
                return expr1
            else:
                expr2.left_expr = expr1
                return expr2
        elif self.tokens_list.lookahead().lexeme_type in {'IDE', 'NRO', 'CAD'}:
            expr1 = self.rel_exp()
            expr2 = self.log_exp()
            if expr2 is None:
                return expr1
            else:
                expr2.left_expr = expr1
                return expr2
        else:
            self.error_treatment('EXPRESSION',
                                 '! ou true ou false ou global ou local ou ( ou Numero ou Identificador ou Cadeira de '
                                 'Caracteres')
        return None

    # Estado usado para iniciar a declaração de uma expressão lógica
    def log_exp(self):
        if self.tokens_list.lookahead().lexeme in {'&&', '||'}:
            token_op = self.logic_symbol()
            expr1 = self.rel_exp()
            expr2 = self.log_exp()
            if expr2 is None:
                return expr.Logical(None, token_op, expr1, self.get_scope())
            else:
                expr2.left_expr = expr1
                return expr.Logical(None, token_op, expr2, self.get_scope())

    # Estado que permite o uso dos símbolos lógicos dentro de uma expressão lógica
    def logic_symbol(self):
        if self.tokens_list.lookahead().lexeme in {'&&', '||'}:
            aux = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            return aux
        else:
            self.error_treatment('LOGICSYMBOL', '&& ou ||')
        return None

    # Estado usado para iniciar a declaração de uma expressão relacional
    def rel_exp(self):
        expr1 = self.arit_exp1()
        expr2 = self.rel_exp2()
        if expr2 is None:
            return expr1
        else:
            expr2.left_expr = expr1
            return expr2

    # Estado usado para auxiliar na declaração de uma expressão relacional
    def rel_exp2(self):
        if self.tokens_list.lookahead().lexeme in {'>', '<', '==', '>=', '<=', '!='}:
            token_op = self.rel_symbol()
            expr1 = self.arit_exp1()
            expr2 = self.rel_exp2()
            if expr2 is None:
                return expr.Binary(None, token_op, expr1, self.get_scope())
            else:
                expr2.left_expr = expr1
                return expr.Binary(None, token_op, expr2, self.get_scope())
        return None

    # Estado que permite o uso dos símbolos relacionais dentro de uma expressão relacional
    def rel_symbol(self):
        if self.tokens_list.lookahead().lexeme in {'>', '<', '==', '>=', '<=', '!='}:
            aux = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            return aux
        else:
            self.error_treatment('RELSYMBOL', '> ou < ou == ou >= ou <= ou !=')
        return None

    # Estado usado para iniciar a declaração de uma expressão aritmética
    def arit_exp1(self):
        expr1 = self.term()
        expr2 = self.arit_exp2()
        if expr2 is None:
            return expr1
        else:
            expr2.left_expr = expr1
            return expr2

    # Estado usado para auxiliar a declaração de uma expressão aritmética
    def arit_exp2(self):
        if self.tokens_list.lookahead().lexeme in {'+', '-'}:
            token_op = self.arit_symb1()
            expr1 = self.term()
            expr2 = self.arit_exp2()
            if expr2 is None:
                return expr.Binary(None, token_op, expr1, self.get_scope())
            else:
                expr2.left_expr = expr1
                return expr.Binary(None, token_op, expr2, self.get_scope())
        return None

    # Estado que permite o uso dos símbolos aritméticos + e - dentro de uma expressão aritmética
    def arit_symb1(self):
        if self.tokens_list.lookahead().lexeme in {'+', '-'}:
            aux = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            return aux
        else:
            self.error_treatment('ARITSYMB1', '+ ou  -')
        return None

    # Estado que permite adicionar uma "subexpressão" ou um valor na expressão que estamos montando
    def term(self):
        expr1 = self.operate()
        expr2 = self.term2()
        if expr2 is None:
            return expr1
        else:
            expr2.left_expr = expr1
            return expr2

    # Estado para verificar se estamos recebendo uma operação de / ou *, por conta da precedência de operadores
    def term2(self):
        if self.tokens_list.lookahead().lexeme in {'*', '/'}:
            token_operator = self.arit_symb2()
            expr1 = self.operate()
            expr2 = self.term2()
            if expr2 is None:
                return expr.Binary(None, token_operator, expr1, self.get_scope())
            else:
                expr2.left_expr = expr1
                return expr.Binary(None, token_operator, expr2, self.get_scope())
        return None

    # Estado que permite o uso dos símbolos aritméticos * e / dentro de uma expressão aritmética
    def arit_symb2(self):
        if self.tokens_list.lookahead().lexeme in {'*', '/'}:
            aux = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            return aux
        else:
            self.error_treatment('ARITSYMB2', '* ou /')
        return None

    # Estado para verificar se estamos recebendo uma valor a ser colocado na expressão ou um abre e fecha parênteses
    def operate(self):
        if self.tokens_list.lookahead().lexeme == '(':
            self.tokens_list.consume_token()
            expr1 = self.expression()
            if self.tokens_list.lookahead().lexeme == ')':
                self.tokens_list.consume_token()
                return expr.Grouping(expr1, self.get_scope())
            else:
                self.error_treatment('OPERATE', ')')
        elif self.tokens_list.lookahead().lexeme in {'true', 'false'}:
            if self.tokens_list.lookahead().lexeme == 'true':
                aux = expr.LiteralVal(True, self.get_scope())
            else:
                aux = expr.LiteralVal(False, self.get_scope())
            self.tokens_list.consume_token()
            return aux
        elif self.tokens_list.lookahead().lexeme_type in {'NRO', 'CAD'}:
            if self.tokens_list.lookahead().lexeme_type == 'NRO':
                if self.tokens_list.lookahead().lexeme.find('.') != -1:
                    aux = expr.LiteralVal(float(self.tokens_list.lookahead().lexeme), self.get_scope())
                else:
                    aux = expr.LiteralVal(int(self.tokens_list.lookahead().lexeme), self.get_scope())
            else:
                aux = expr.LiteralVal(self.tokens_list.lookahead().lexeme, self.get_scope())
            self.tokens_list.consume_token()
            return aux
        elif self.tokens_list.lookahead().lexeme_type == 'IDE':
            ide = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            aux = self.cont_operate()
            if isinstance(aux, expr.FunctionCall):
                aux.func_exp = ide
            elif aux is None:
                aux = expr.ConstVarAccess(ide, self.get_scope())
            elif isinstance(aux, expr.ConstVarAccess):
                aux.token_name = ide
            elif isinstance(aux, expr.StructGet):
                aux.struct_name = expr.ConstVarAccess(ide, self.get_scope())
            return aux
        elif self.tokens_list.lookahead().lexeme in {'global', 'local'}:
            return self.scope_variable()
        else:
            self.error_treatment('OPERATE',
                                 '( ou true ou false ou glocal ou local ou Identificador ou Numero ou Cadeia de '
                                 'Caracteres')
        return None

    # Estado que permite fazer chamadas de função ou outra variável para ser usada dentro da expressão
    def cont_operate(self):
        if self.tokens_list.lookahead().lexeme == '(':
            return self.function_call()
        else:
            return self.cont_element()

# =====================================================================================================================
# ============================================== Typedef declaration ==================================================

    # Estado que inicia a declaração de um typedef
    def typedef_declaration(self):
        if self.tokens_list.lookahead().lexeme == 'typedef':
            self.Line.tp = 'typedef'
            self.Line.program_line = self.tokens_list.lookahead().file_line
            self.tokens_list.consume_token()
            return self.cont_typedef_dec()
        else:
            self.error_treatment('TYPEDEFDECLARATION', 'typedef')
            return None

    # Estado auxiliar na declaração de um typedef
    def cont_typedef_dec(self):
        if self.tokens_list.lookahead().lexeme == 'struct':
            self.Line.data_type = 'struct'
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                self.Line.data_type += '.' + self.tokens_list.lookahead().lexeme
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme_type == 'IDE':
                    temp = self.tokens_list.lookahead()
                    self.Line.name = self.tokens_list.lookahead().lexeme
                    self.tokens_list.consume_token()
                    if self.tokens_list.lookahead().lexeme == ';':
                        aux = stmt.Typedef(temp, self.Line.data_type, self.get_scope())
                        self.add_line_on_table(0)
                        self.tokens_list.consume_token()
                        return aux
                    else:
                        self.error_treatment('CONTTYPEDEFDEC', ';')
                else:
                    self.error_treatment('CONTTYPEDEFDEC', 'Identificador')
            else:
                self.error_treatment('CONTTYPEDEFDEC', 'Identificador')
        elif self.tokens_list.lookahead().lexeme_type == 'IDE' or self.tokens_list.lookahead().lexeme in {
                'int', 'real', 'string', 'boolean'}:
            self.data_type()
            if self.tokens_list.lookahead().lexeme_type == 'IDE':
                temp = self.tokens_list.lookahead()
                self.Line.name = self.tokens_list.lookahead().lexeme
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == ';':
                    aux = stmt.Typedef(temp, self.Line.data_type, self.get_scope())
                    self.add_line_on_table(0)
                    self.tokens_list.consume_token()
                    return aux
                else:
                    self.error_treatment('CONTTYPEDEFDEC', ';')
            else:
                self.error_treatment('CONTTYPEDEFDEC', 'Identificador')
        else:
            self.error_treatment('CONTTYPEDEFDEC', 'struct ou int ou real ou string ou boolean ou Identificador')
        return None

# =====================================================================================================================
# ================================================== Procedures =======================================================

    # Estado utilizado para a criação de um procedure start
    def start_procedure(self):
        if self.tokens_list.lookahead().lexeme == '(':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == ')':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    aux = deepcopy(self.Line)
                    self.add_line_on_table(0)
                    self.add_new_symb_table(aux)
                    self.global_scope = False
                    self.proc_stmt.scope = self.get_scope()
                    self.proc_content()
                else:
                    self.error_treatment('STARTPROCEDURE', '{')
            else:
                self.error_treatment('STARTPROCEDURE', ')')
        else:
            self.error_treatment('STARTPROCEDURE', '(')

    # Estado utilizado para a criação de um procedure qualquer
    def procedure(self):
        if self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.Line.name = self.tokens_list.lookahead().lexeme
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '(':
                self.tokens_list.consume_token()
                self.proc_param()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    aux = deepcopy(self.Line)
                    self.add_line_on_table(0)
                    self.add_new_symb_table(aux)
                    self.global_scope = False
                    self.proc_content()
                else:
                    self.error_treatment('PROCEDURE', '{')
            else:
                self.error_treatment('PROCEDURE', '(')
        else:
            self.error_treatment('PROCEDURE', 'Identificador')

    # Estado que permite a adição de nenhum ou vários parâmetros para esse procedure
    def proc_param(self):
        if self.tokens_list.lookahead().lexeme == ')':
            self.tokens_list.consume_token()
            self.proc_stmt.params = self.Line.params
        elif self.tokens_list.lookahead().lexeme in {
                'struct', 'int', 'real', 'string', 'boolean'} or self.tokens_list.lookahead().lexeme_type == 'IDE':
            self.parameters()
        else:
            self.error_treatment('PROCPARAM', ') ou struct ou int ou real ou string ou boolean ou Identificador')

    # Definição do conteúdo interno do bloco da procedure: permite uma ou nenhuma declaração de constante e variável
    # antes das demais linhas de código
    def proc_content(self):
        if self.tokens_list.lookahead().lexeme == 'var':
            self.proc_stmt.body.append(self.var_declaration())
            self.proc_content2()
        elif self.tokens_list.lookahead().lexeme == 'const':
            self.proc_stmt.body.append(self.const_declaration())
            self.proc_content3()
        else:
            code_lines = self.code()
            if code_lines is not None:
                self.proc_stmt.body.extend(code_lines)
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
                self.global_scope = True
            else:
                self.error_treatment('PROCCONTENT', '}')

    # Estado que permite apenas declaração de constante, assumindo que um bloco var foi declarado anteriormente
    def proc_content2(self):
        if self.tokens_list.lookahead().lexeme == 'const':
            self.proc_stmt.body.append(self.const_declaration())
            self.proc_content4()
        else:
            temp = self.code()
            if temp is not None:
                self.proc_stmt.body.extend(temp)
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
                self.global_scope = True
            else:
                self.error_treatment('PROCCONTENT2', '}')

    # Estado que permite apenas declaração de variável, assumindo que um bloco const foi declarado anteriormente
    def proc_content3(self):
        if self.tokens_list.lookahead().lexeme == 'var':
            self.proc_stmt.body.append(self.var_declaration())
            self.proc_content4()
        else:
            self.proc_stmt.body.extend(self.code())
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
                self.global_scope = True
            else:
                self.error_treatment('PROCCONTENT3', '}')

    # Código interno de um procedure
    def proc_content4(self):
        self.proc_stmt.body.extend(self.code())
        if self.tokens_list.lookahead().lexeme == '}':
            self.tokens_list.consume_token()
            self.global_scope = True
        else:
            self.error_treatment('PROCCONTENT4', '}')

    # Estado utilizado para fazer o loop que permite a adição de diferentes expressões, comandos e etc
    def code(self):
        if self.tokens_list.lookahead().lexeme in {
            'global', 'local', 'struct', 'typedef', '++', '--', 'print', 'read', 'while',
                'if'} or self.tokens_list.lookahead().lexeme_type == 'IDE':
            aux = self.command()
            temp = self.code()
            if temp is not None:
                if isinstance(temp, list):
                    list_temp = [aux]
                    list_temp.extend(temp)
                    return list_temp
                else:
                    return [aux, temp]
            else:
                return [aux]
        return None

    # Tipos de comandos que podem ser utilizados dentro de uma function ou uma procedure
    def command(self):
        if self.tokens_list.lookahead().lexeme == 'print':
            return self.print_func()
        elif self.tokens_list.lookahead().lexeme_type == 'IDE':
            aux = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            temp = self.other_commands()
            if isinstance(temp, expr.FunctionCall):
                temp.func_exp = aux
            elif isinstance(temp, expr.Assign):
                if isinstance(temp.token, expr.ConstVarAccess):
                    temp.token.token_name = aux
                elif isinstance(temp.token, expr.StructGet):
                    temp.token.struct_name = expr.ConstVarAccess(aux, self.get_scope())
                elif temp.token is None:
                    temp.token = expr.ConstVarAccess(aux, self.get_scope())
            elif isinstance(temp, expr.PrePosIncDec):
                if temp.variable:
                    if isinstance(temp.variable, expr.StructGet):
                        temp.variable.struct_name = expr.ConstVarAccess(aux, self.get_scope())
                    elif isinstance(temp.variable, expr.ConstVarAccess):
                        temp.variable.token_name = aux
                else:
                    temp.variable = expr.ConstVarAccess(aux, self.get_scope())
            return temp
        elif self.tokens_list.lookahead().lexeme in {'global', 'local'}:
            aux = self.scope_variable()
            temp = self.other_commands()
            if isinstance(temp, expr.FunctionCall):
                temp.func_exp = aux
            elif isinstance(temp, expr.Assign):
                if isinstance(temp.token, expr.ConstVarAccess):
                    temp.token.token_name = aux
                elif isinstance(temp.token, expr.StructGet):
                    temp.token.struct_name = aux
                elif temp.token is None:
                    temp.token = aux
            elif isinstance(temp, expr.PrePosIncDec):
                temp.variable = aux
            return temp
        elif self.tokens_list.lookahead().lexeme == 'read':
            return self.read()
        elif self.tokens_list.lookahead().lexeme == 'while':
            return self.while_func()
        elif self.tokens_list.lookahead().lexeme == 'if':
            return self.conditional()
        elif self.tokens_list.lookahead().lexeme == 'typedef':
            return self.typedef_declaration()
        elif self.tokens_list.lookahead().lexeme == 'struct':
            return self.structure_declaration()
        elif self.tokens_list.lookahead().lexeme in {'++', '--'}:
            aux = expr.PrePosIncDec(self.tokens_list.lookahead(), None, self.get_scope())
            self.tokens_list.consume_token()
            aux.variable = self.variable()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
                return aux
        else:
            self.error_treatment('COMMAND',
                                 'print ou Identificador ou global ou local ou read ou while ou if ou typedef ou '
                                 'struct ou ++ ou --')

    # Outros tipos de de comandos que podem ser utilizados dentro de uma function ou uma procedure, que podem ser uma
    # chamada de função ou menção a um identificador
    def other_commands(self):
        if self.tokens_list.lookahead().lexeme == '(':
            temp = self.function_call()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
                return temp
            else:
                self.error_treatment('OTHERCOMMANDS', ';')
        else:
            temp = self.cont_element()
            temp2 = self.other_commands2()
            if temp is None:
                return temp2
            if isinstance(temp2, expr.Assign):
                temp2.token = temp
            elif isinstance(temp2, expr.PrePosIncDec):
                temp2.variable = temp
            return temp2

    # Outros tipos de de comandos que podem ser utilizados dentro de uma function ou uma procedure: pode ser
    # pré/pós incremento (++), pré/pós decremento (--) ou uma atribuição
    def other_commands2(self):
        if self.tokens_list.lookahead().lexeme in {'++', '--'}:
            temp = expr.PrePosIncDec(self.tokens_list.lookahead(), None, self.get_scope())
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
                return temp
            else:
                self.error_treatment('OTHERCOMMANDS2', ';')

        elif self.tokens_list.lookahead().lexeme == '=':
            return self.assignment()
        else:
            self.error_treatment('OTHERCOMMANDS2', '++ ou -- ou =')
        return None

# =====================================================================================================================
# ================================================ Print function =====================================================

    # Estado usado para a chamada do comando print
    def print_func(self):
        print_stmt = stmt.Printf(None, self.get_scope(), None)
        if self.tokens_list.lookahead().lexeme == 'print':
            print_stmt.program_line = self.tokens_list.lookahead().file_line
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '(':
                self.tokens_list.consume_token()
                print_stmt.expression = self.printable_list()
            else:
                self.error_treatment('PRINTFUNC', '(')
        else:
            self.error_treatment('PRINTFUNC', 'print')
        return print_stmt

    # Estado usado para montar a lista de parâmetros do comando print
    def printable_list(self):
        itens = []
        itens.append(self.printable())
        temp = self.next_print_value()
        if temp is not None:
            itens.extend(temp)
        return itens

    # Estado que define quais elementos podem ser usados como parâmetros do comando print
    def printable(self):
        return self.expression()

    # Estado utilizado para permitir que mais de um valor seja passado como parâmetro para o método print
    def next_print_value(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            return self.printable_list()
        elif self.tokens_list.lookahead().lexeme == ')':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
            else:
                self.error_treatment('NEXTPRINTVALUE', ';')
        else:
            self.error_treatment('NEXTPRINTVALUE', ', ou )')
        return None

# =====================================================================================================================
# ============================================= Variable assignment ===================================================

    # Estado usado para fazer a atribuição de valores a uma variável
    def assignment(self):
        assign_expr = expr.Assign(None, None, self.get_scope())
        if self.tokens_list.lookahead().lexeme == '=':
            self.tokens_list.consume_token()
            assign_expr.expr = self.expression()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
            else:
                self.error_treatment('ASSIGNMENT', ';')
        else:
            self.error_treatment('ASSIGNMENT', '=')
        return assign_expr

# =====================================================================================================================
# ================================================ Function call ======================================================

    # Estado utilizado para permitir a chamada de funções no nosso código
    def function_call(self):
        if self.tokens_list.lookahead().lexeme == '(':
            self.tokens_list.consume_token()
            args = self.cont_f_call()
            if isinstance(args, tk.Token):
                return expr.FunctionCall(None, None, args, self.get_scope())
            else:
                return args
        else:
            self.error_treatment('FUNCTIONCALL', '(')

    # Estado para auxiliar a adição de parâmetros para as chamadas de função
    def cont_f_call(self):
        if self.tokens_list.lookahead().lexeme == ')':
            parent = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            return parent
        elif self.tokens_list.lookahead().lexeme in {
            'true', 'false', 'global', 'local', '(', '!'} or self.tokens_list.lookahead().lexeme_type in {
                'NRO', 'IDE', 'CAD'}:
            arg1 = self.expression()
            arg2 = self.f_call_params()
            if isinstance(arg2, tk.Token):
                return expr.FunctionCall([arg1], None, arg2, self.get_scope())
            elif isinstance(arg2, expr.FunctionCall):
                arg2.arguments.insert(0, arg1)
                return arg2
        else:
            self.error_treatment('CONTFCALL',
                                 ') ou true ou false ou global ou local ou ( ou ! ou Numero ou Identificador ou '
                                 'Cadeia de Caracteres')
        return None

    # Loop que permite adicionar mais de um parâmetros para uma chamada de função
    def f_call_params(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            arg1 = self.expression()
            arg2 = self.f_call_params()
            if isinstance(arg2, tk.Token):
                return expr.FunctionCall([arg1], None, arg2, self.get_scope())
            elif isinstance(arg2, expr.FunctionCall):
                arg2.arguments.insert(0, arg1)
                return arg2

        elif self.tokens_list.lookahead().lexeme == ')':
            parent = self.tokens_list.lookahead()
            self.tokens_list.consume_token()
            return parent
        else:
            self.error_treatment('FCALLPARAMS', ', ou )')

# =====================================================================================================================
# ================================================= Read method =======================================================

    def read(self):
        read_stmt = stmt.Read(None, self.get_scope())
        if self.tokens_list.lookahead().lexeme == 'read':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '(':
                self.tokens_list.consume_token()
                read_stmt.params = self.read_params()
            else:
                self.error_treatment('READ', '(')
        else:
            self.error_treatment('READ', 'read')
        return read_stmt

    def read_params(self):
        itens = []
        itens.append(self.variable())
        temp = self.read_loop()
        if temp is not None:
            itens.extend(temp)
        return itens

    def read_loop(self):
        if self.tokens_list.lookahead().lexeme == ',':
            self.tokens_list.consume_token()
            return self.read_params()
        elif self.tokens_list.lookahead().lexeme == ')':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
            else:
                self.error_treatment('READLOOP', ';')
        else:
            self.error_treatment('READLOOP', ', ou )')
        return None

# =====================================================================================================================
# ================================================= While method ======================================================
    def while_func(self):
        while_stmt = stmt.While(None, None, self.get_scope(), None)
        if self.tokens_list.lookahead().lexeme == 'while':
            while_stmt.program_line = self.tokens_list.lookahead().file_line
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '(':
                self.tokens_list.consume_token()
                while_stmt.condition = self.expression()
                if self.tokens_list.lookahead().lexeme == ')':
                    self.tokens_list.consume_token()
                    if self.tokens_list.lookahead().lexeme == '{':
                        self.tokens_list.consume_token()
                        while_stmt.body = self.code()
                        if self.tokens_list.lookahead().lexeme == '}':
                            self.tokens_list.consume_token()
                        else:
                            self.error_treatment('WHILEFUNC', '}')
                    else:
                        self.error_treatment('WHILEFUNC', '{')
                else:
                    self.error_treatment('WHILEFUNC', ')')
            else:
                self.error_treatment('WHILEFUNC', '(')
        else:
            self.error_treatment('WHILEFUNC', 'while')
        return while_stmt

# =====================================================================================================================
# ================================================ If..then..else =====================================================
    def conditional(self):
        if_stmt = stmt.IfThenElse(None, None, None, self.get_scope(), None)
        if self.tokens_list.lookahead().lexeme == 'if':
            if_stmt.program_line = self.tokens_list.lookahead().file_line
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '(':
                self.tokens_list.consume_token()
                if_stmt.cond_expr = self.expression()
                if self.tokens_list.lookahead().lexeme == ')':
                    self.tokens_list.consume_token()
                    if self.tokens_list.lookahead().lexeme == 'then':
                        self.tokens_list.consume_token()
                        if self.tokens_list.lookahead().lexeme == '{':
                            self.tokens_list.consume_token()
                            if_stmt.then_branch = self.code()
                            if self.tokens_list.lookahead().lexeme == '}':
                                self.tokens_list.consume_token()
                                temp = self.else_part()
                                if temp is not None:
                                    if_stmt.else_branch = temp
                            else:
                                self.error_treatment('CONDITIONAL', '}')
                        else:
                            self.error_treatment('CONDITIONAL', '{')
                    else:
                        self.error_treatment('CONDITIONAL', 'then')
                else:
                    self.error_treatment('CONDITIONAL', ')')
            else:
                self.error_treatment('CONDITIONAL', '(')
        else:
            self.error_treatment('CONDITIONAL', 'if')
        return if_stmt

    def else_part(self):
        if self.tokens_list.lookahead().lexeme == 'else':
            self.tokens_list.consume_token()
            if self.tokens_list.lookahead().lexeme == '{':
                self.tokens_list.consume_token()
                temp = self.code()
                if self.tokens_list.lookahead().lexeme == '}':
                    self.tokens_list.consume_token()
                    return temp
                else:
                    self.error_treatment('ELSEPART', '}')
            else:
                self.error_treatment('ELSEPART', '{')
        return None

# =====================================================================================================================
# =============================================== Erros treatment =====================================================
    def error_treatment(self, state, expected_token):
        self.error = True
        self.output_list.add_token('ERRO SINTATICO ESPERAVA: ' + expected_token
                                   + ' E RECEBI:', self.tokens_list.lookahead().lexeme,
                                   self.tokens_list.lookahead().file_line)
        state_firsts = f.FirstsFollows.getFirsts(state)
        state_follows = f.FirstsFollows.getFollows(state)
        if state == 'STRUCTVAREXP' or state == 'STRUCTMATRIX' or state == 'CONTSTRUCTMATRIX':
            self.next_struct_var()
        elif state == 'VAREXP' or state == 'STRUCTURE' or state == 'CONTMATRIX' or state == 'VERIFVAR':
            self.next_var()
        elif state == 'VERIFCONST':
            self.next_const()
        elif expected_token.find('{') != -1:
            if state == 'STRUCTVARS':
                if self.tokens_list.lookahead().lexeme == 'var':
                    self.missing_open_key(state)
            else:
                self.missing_open_key(state)
        elif expected_token.find('(') != -1:
            self.missing_open_parenthesis(state)
        elif expected_token.find(')') != -1 and state in {'CONDITIONAL', 'STARTPROCEDURE', 'WHILEFUNC'}:
            self.missing_closing_parenthesis(state)
        elif expected_token.find('then') != -1 and state == 'CONDITIONAL' \
                and self.tokens_list.lookahead().lexeme == '{':
            self.missing_then()
        else:
            while self.tokens_list.lookahead().lexeme not in state_follows and \
                    self.tokens_list.lookahead().lexeme_type not in state_follows and \
                    self.tokens_list.lookahead().lexeme not in state_firsts and\
                    self.tokens_list.lookahead().lexeme_type not in state_firsts and\
                    self.tokens_list.lookahead().lexeme != 'endOfFile($)':
                self.tokens_list.consume_token()
            if (self.tokens_list.lookahead().lexeme in state_firsts or
                    self.tokens_list.lookahead().lexeme_type in state_firsts) and\
                    state != 'BLOCKFUNCTION':
                getattr(self, inspect.currentframe().f_back.f_code.co_name)()

    def missing_open_key(self, state):
        if state == 'VARDECLARATION':
            self.first_var()
        elif state == 'CONSTDECLARATION':
            self.first_const()
        elif state == 'BLOCKFUNCTION':
            self.block_function_content()
            if self.tokens_list.lookahead().lexeme == ';':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '}':
                    self.tokens_list.consume_token()
                else:
                    self.error_treatment('BLOCKFUNCTION', '}')
            else:
                self.error_treatment('BLOCKFUNCTION', ';')
        elif state in {'PROCEDURE', 'STARTPROCEDURE'}:
            self.proc_content()
        elif state == 'CONDITIONAL':
            self.code()
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
                self.else_part()
            else:
                self.error_treatment('CONDITIONAL', '}')
        elif state == 'WHILEFUNC':
            self.code()
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
            else:
                self.error_treatment('WHILEFUNC', '}')
        elif state == 'STRUCTVARS':
            if self.tokens_list.lookahead().lexeme == 'var':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    self.first_struct_var()
                else:
                    self.error_treatment('STRUCTVARS', '{')
            else:
                self.error_treatment('STRUCTVARS', 'var')
        elif state == 'ELSEPART':
            self.code()
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
            else:
                self.error_treatment('ELSEPART', '}')

    def missing_open_parenthesis(self, state):
        if state == 'FUNCTION':
            self.continue_function()
        elif state == 'WHILEFUNC':
            self.expression()
            if self.tokens_list.lookahead().lexeme == ')':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    self.code()
                    if self.tokens_list.lookahead().lexeme == '}':
                        self.tokens_list.consume_token()
                    else:
                        self.error_treatment('WHILEFUNC', '}')
                else:
                    self.error_treatment('WHILEFUNC', '{')
            else:
                self.error_treatment('WHILEFUNC', ')')
        elif state == 'READ':
            self.read_params()
        elif state == 'PRINTFUNC':
            self.printable_list()
        elif state == 'STARTPROCEDURE':
            if self.tokens_list.lookahead().lexeme == ')':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    self.proc_content()
                else:
                    self.error_treatment('STARTPROCEDURE', '{')
            else:
                self.error_treatment('STARTPROCEDURE', ')')
        elif state == 'CONDITIONAL':
            self.expression()
            if self.tokens_list.lookahead().lexeme == ')':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == 'then':
                    self.tokens_list.consume_token()
                    if self.tokens_list.lookahead().lexeme == '{':
                        self.tokens_list.consume_token()
                        self.code()
                        if self.tokens_list.lookahead().lexeme == '}':
                            self.tokens_list.consume_token()
                            self.else_part()
                        else:
                            self.error_treatment('CONDITIONAL', '}')
                    else:
                        self.error_treatment('CONDITIONAL', '{')
                else:
                    self.error_treatment('CONDITIONAL', 'then')
        elif state == 'PROCEDURE':
            self.proc_param()
            if self.tokens_list.lookahead().lexeme == '{':
                self.tokens_list.consume_token()
                self.proc_content()
            else:
                self.error_treatment('PROCEDURE', '{')

    def missing_closing_parenthesis(self, state):
        if state == 'WHILEFUNC':
            if self.tokens_list.lookahead().lexeme == '{':
                self.tokens_list.consume_token()
                self.code()
                if self.tokens_list.lookahead().lexeme == '}':
                    self.tokens_list.consume_token()
                else:
                    self.error_treatment('WHILEFUNC', '}')
            else:
                self.error_treatment('WHILEFUNC', '{')
        elif state == 'STARTPROCEDURE':
            if self.tokens_list.lookahead().lexeme == '{':
                self.tokens_list.consume_token()
                self.proc_content()
            else:
                self.error_treatment('STARTPROCEDURE', '{')
        elif state == 'CONDITIONAL':
            if self.tokens_list.lookahead().lexeme == 'then':
                self.tokens_list.consume_token()
                if self.tokens_list.lookahead().lexeme == '{':
                    self.tokens_list.consume_token()
                    self.code()
                    if self.tokens_list.lookahead().lexeme == '}':
                        self.tokens_list.consume_token()
                        self.else_part()
                    else:
                        self.error_treatment('CONDITIONAL', '}')
                else:
                    self.error_treatment('CONDITIONAL', '{')
            else:
                self.error_treatment('CONDITIONAL', 'then')

    def missing_then(self):
        if self.tokens_list.lookahead().lexeme == '{':
            self.tokens_list.consume_token()
            self.code()
            if self.tokens_list.lookahead().lexeme == '}':
                self.tokens_list.consume_token()
                self.else_part()
            else:
                self.error_treatment('CONDITIONAL', '}')
        else:
            self.error_treatment('CONDITIONAL', '{')

    def get_scope(self):
        if self.global_scope:
            return -1
        else:
            return self.scope_index
