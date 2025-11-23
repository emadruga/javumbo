"""
Verbal Tenses Sample Deck Generator

Generates a comprehensive set of English verbal tense flashcards with Portuguese translations.
This is the default "sample deck" added to new user databases.

Extracted from the original monolithic app.py to keep the main application clean.
"""

import hashlib
import sqlite3
import time
import uuid


def sha1_checksum(data):
    """Calculates the SHA1 checksum for Anki note syncing."""
    return hashlib.sha1(data.encode('utf-8')).hexdigest()


def generate_verbal_tenses_flashcards():
    """
    Generates a list of flashcards about verbal tenses in English.

    Each flashcard has:
    - Front: English example sentence
    - Back: (a) Portuguese translation, (b) Tense name, (c) Usage explanation in Portuguese

    Returns:
        list: List of (front, back) tuples ready for insertion into Anki database
    """
    # Define the structure of verbal tenses
    tenses = [
        # Simple Present
        {
            "name": "Simple Present: I work",
            "usage": "Usage: For habits, routines, facts, and general truths.",
            "usage_pt": "Uso: Para hábitos, rotinas, fatos e verdades gerais.",
            "examples": [
                {"en": "She plays tennis every weekend.", "pt": "Ela joga tênis todos os fins de semana."},
                {"en": "The sun rises in the east.", "pt": "O sol nasce no leste."},
                {"en": "They live in New York.", "pt": "Eles moram em Nova York."}
            ]
        },
        {
            "name": "Simple Present: Negatives",
            "usage": "Form: Subject + do/does + not + verb",
            "usage_pt": "Forma: Sujeito + do/does + not + verbo",
            "examples": [
                {"en": "I do not (don't) speak French.", "pt": "Eu não falo francês."},
                {"en": "He does not (doesn't) own a car.", "pt": "Ele não possui um carro."},
                {"en": "They do not (don't) like coffee.", "pt": "Eles não gostam de café."}
            ]
        },
        {
            "name": "Simple Present: Questions",
            "usage": "Form: Do/Does + subject + verb?",
            "usage_pt": "Forma: Do/Does + sujeito + verbo?",
            "examples": [
                {"en": "Do you enjoy swimming?", "pt": "Você gosta de nadar?"},
                {"en": "Does she work here?", "pt": "Ela trabalha aqui?"},
                {"en": "Do they understand the rules?", "pt": "Eles entendem as regras?"}
            ]
        },

        # Present Continuous/Progressive
        {
            "name": "Present Continuous: I am working",
            "usage": "Usage: For actions happening now or around now, and temporary situations.",
            "usage_pt": "Uso: Para ações acontecendo agora ou por volta de agora, e situações temporárias.",
            "examples": [
                {"en": "She is studying for her exam.", "pt": "Ela está estudando para o exame dela."},
                {"en": "They are building a new house this year.", "pt": "Eles estão construindo uma casa nova este ano."},
                {"en": "I am learning to play the guitar.", "pt": "Eu estou aprendendo a tocar guitarra."}
            ]
        },
        {
            "name": "Present Continuous: Negatives",
            "usage": "Form: Subject + am/is/are + not + verb-ing",
            "usage_pt": "Forma: Sujeito + am/is/are + not + verbo-ing",
            "examples": [
                {"en": "He is not (isn't) sleeping right now.", "pt": "Ele não está dormindo agora."},
                {"en": "We are not (aren't) having dinner yet.", "pt": "Nós não estamos jantando ainda."},
                {"en": "I am not waiting any longer.", "pt": "Eu não estou esperando mais."}
            ]
        },
        {
            "name": "Present Continuous: Questions",
            "usage": "Form: Am/Is/Are + subject + verb-ing?",
            "usage_pt": "Forma: Am/Is/Are + sujeito + verbo-ing?",
            "examples": [
                {"en": "Are you listening to me?", "pt": "Você está me ouvindo?"},
                {"en": "Is it raining outside?", "pt": "Está chovendo lá fora?"},
                {"en": "Are they coming to the party?", "pt": "Eles estão vindo para a festa?"}
            ]
        },

        # Present Perfect
        {
            "name": "Present Perfect: I have worked",
            "usage": "Usage: For past actions with present results, experiences, and unfinished time periods.",
            "usage_pt": "Uso: Para ações passadas com resultados presentes, experiências e períodos de tempo inacabados.",
            "examples": [
                {"en": "I have visited Paris twice.", "pt": "Eu já visitei Paris duas vezes."},
                {"en": "She has lived here for five years.", "pt": "Ela tem morado aqui por cinco anos."},
                {"en": "They have already finished their homework.", "pt": "Eles já terminaram a lição de casa."}
            ]
        },
        {
            "name": "Present Perfect: Negatives",
            "usage": "Form: Subject + have/has + not + past participle",
            "usage_pt": "Forma: Sujeito + have/has + not + particípio passado",
            "examples": [
                {"en": "I have not (haven't) seen that movie.", "pt": "Eu não vi esse filme."},
                {"en": "She has not (hasn't) called me back.", "pt": "Ela não me ligou de volta."},
                {"en": "We have not (haven't) been to that restaurant.", "pt": "Nós não fomos àquele restaurante."}
            ]
        },
        {
            "name": "Present Perfect: Questions",
            "usage": "Form: Have/Has + subject + past participle?",
            "usage_pt": "Forma: Have/Has + sujeito + particípio passado?",
            "examples": [
                {"en": "Have you ever climbed a mountain?", "pt": "Você já escalou uma montanha?"},
                {"en": "Has he sent the email?", "pt": "Ele enviou o email?"},
                {"en": "Have they arrived yet?", "pt": "Eles já chegaram?"}
            ]
        },

        # Present Perfect Continuous
        {
            "name": "Present Perfect Continuous: I have been working",
            "usage": "Usage: For ongoing actions that started in the past and continue to the present, often emphasizing duration.",
            "usage_pt": "Uso: Para ações contínuas que começaram no passado e continuam até o presente, frequentemente enfatizando a duração.",
            "examples": [
                {"en": "I have been waiting for an hour.", "pt": "Eu estou esperando há uma hora."},
                {"en": "She has been teaching since 2010.", "pt": "Ela está ensinando desde 2010."},
                {"en": "They have been traveling all month.", "pt": "Eles estão viajando o mês todo."}
            ]
        },
        {
            "name": "Present Perfect Continuous: Negatives",
            "usage": "Form: Subject + have/has + not + been + verb-ing",
            "usage_pt": "Forma: Sujeito + have/has + not + been + verbo-ing",
            "examples": [
                {"en": "I have not (haven't) been feeling well.", "pt": "Eu não tenho me sentido bem."},
                {"en": "He has not (hasn't) been working lately.", "pt": "Ele não tem trabalhado ultimamente."},
                {"en": "They have not (haven't) been studying enough.", "pt": "Eles não têm estudado o suficiente."}
            ]
        },
        {
            "name": "Present Perfect Continuous: Questions",
            "usage": "Form: Have/Has + subject + been + verb-ing?",
            "usage_pt": "Forma: Have/Has + sujeito + been + verbo-ing?",
            "examples": [
                {"en": "Have you been exercising regularly?", "pt": "Você tem se exercitado regularmente?"},
                {"en": "Has she been living alone?", "pt": "Ela tem morado sozinha?"},
                {"en": "Have they been practicing for the concert?", "pt": "Eles têm praticado para o concerto?"}
            ]
        },

        # Simple Past
        {
            "name": "Simple Past: I worked",
            "usage": "Usage: For completed actions in the past.",
            "usage_pt": "Uso: Para ações completas no passado.",
            "examples": [
                {"en": "She visited her grandmother last week.", "pt": "Ela visitou a avó dela na semana passada."},
                {"en": "They bought a new car yesterday.", "pt": "Eles compraram um carro novo ontem."},
                {"en": "I watched a movie last night.", "pt": "Eu assisti um filme ontem à noite."}
            ]
        },
        {
            "name": "Simple Past: Negatives",
            "usage": "Form: Subject + did + not + verb",
            "usage_pt": "Forma: Sujeito + did + not + verbo",
            "examples": [
                {"en": "I did not (didn't) go to the party.", "pt": "Eu não fui à festa."},
                {"en": "She did not (didn't) like the book.", "pt": "Ela não gostou do livro."},
                {"en": "They did not (didn't) finish their work.", "pt": "Eles não terminaram o trabalho deles."}
            ]
        },
        {
            "name": "Simple Past: Questions",
            "usage": "Form: Did + subject + verb?",
            "usage_pt": "Forma: Did + sujeito + verbo?",
            "examples": [
                {"en": "Did you call him?", "pt": "Você ligou para ele?"},
                {"en": "Did she arrive on time?", "pt": "Ela chegou na hora?"},
                {"en": "Did they win the game?", "pt": "Eles ganharam o jogo?"}
            ]
        },

        # Past Continuous/Progressive
        {
            "name": "Past Continuous: I was working",
            "usage": "Usage: For actions in progress at a specific time in the past, often interrupted by another action.",
            "usage_pt": "Uso: Para ações em progresso em um momento específico no passado, frequentemente interrompidas por outra ação.",
            "examples": [
                {"en": "I was reading when the phone rang.", "pt": "Eu estava lendo quando o telefone tocou."},
                {"en": "They were having dinner at 8 PM.", "pt": "Eles estavam jantando às 8 da noite."},
                {"en": "She was sleeping when I came home.", "pt": "Ela estava dormindo quando eu cheguei em casa."}
            ]
        },
        {
            "name": "Past Continuous: Negatives",
            "usage": "Form: Subject + was/were + not + verb-ing",
            "usage_pt": "Forma: Sujeito + was/were + not + verbo-ing",
            "examples": [
                {"en": "I was not (wasn't) listening carefully.", "pt": "Eu não estava ouvindo com atenção."},
                {"en": "They were not (weren't) expecting visitors.", "pt": "Eles não estavam esperando visitantes."},
                {"en": "She was not (wasn't) driving fast.", "pt": "Ela não estava dirigindo rápido."}
            ]
        },
        {
            "name": "Past Continuous: Questions",
            "usage": "Form: Was/Were + subject + verb-ing?",
            "usage_pt": "Forma: Was/Were + sujeito + verbo-ing?",
            "examples": [
                {"en": "Were you waiting for me?", "pt": "Você estava esperando por mim?"},
                {"en": "Was he telling the truth?", "pt": "Ele estava dizendo a verdade?"},
                {"en": "Were they working late?", "pt": "Eles estavam trabalhando até tarde?"}
            ]
        },

        # Past Perfect
        {
            "name": "Past Perfect: I had worked",
            "usage": "Usage: For actions completed before another past action or time.",
            "usage_pt": "Uso: Para ações completadas antes de outra ação passada ou tempo.",
            "examples": [
                {"en": "I had finished dinner before she called.", "pt": "Eu tinha terminado o jantar antes de ela ligar."},
                {"en": "They had left before I arrived.", "pt": "Eles tinham saído antes de eu chegar."},
                {"en": "She had studied Spanish before moving to Madrid.", "pt": "Ela tinha estudado espanhol antes de se mudar para Madri."}
            ]
        },
        {
            "name": "Past Perfect: Negatives",
            "usage": "Form: Subject + had + not + past participle",
            "usage_pt": "Forma: Sujeito + had + not + particípio passado",
            "examples": [
                {"en": "I had not (hadn't) seen the movie before.", "pt": "Eu não tinha visto o filme antes."},
                {"en": "She had not (hadn't) completed her work.", "pt": "Ela não tinha completado o trabalho dela."},
                {"en": "They had not (hadn't) heard the news.", "pt": "Eles não tinham ouvido as notícias."}
            ]
        },
        {
            "name": "Past Perfect: Questions",
            "usage": "Form: Had + subject + past participle?",
            "usage_pt": "Forma: Had + sujeito + particípio passado?",
            "examples": [
                {"en": "Had you met him before?", "pt": "Você tinha conhecido ele antes?"},
                {"en": "Had she ever visited London?", "pt": "Ela já tinha visitado Londres?"},
                {"en": "Had they received my message?", "pt": "Eles tinham recebido minha mensagem?"}
            ]
        },

        # Past Perfect Continuous
        {
            "name": "Past Perfect Continuous: I had been working",
            "usage": "Usage: For ongoing actions that started before and continued up to another time in the past, emphasizing duration.",
            "usage_pt": "Uso: Para ações contínuas que começaram antes e continuaram até outro momento no passado, enfatizando a duração.",
            "examples": [
                {"en": "I had been studying for three hours when she called.", "pt": "Eu estava estudando há três horas quando ela ligou."},
                {"en": "They had been living there for years before they moved.", "pt": "Eles estavam morando lá por anos antes de se mudarem."},
                {"en": "She had been working all day before she went home.", "pt": "Ela estava trabalhando o dia todo antes de ir para casa."}
            ]
        },
        {
            "name": "Past Perfect Continuous: Negatives",
            "usage": "Form: Subject + had + not + been + verb-ing",
            "usage_pt": "Forma: Sujeito + had + not + been + verbo-ing",
            "examples": [
                {"en": "I had not (hadn't) been sleeping well before the exam.", "pt": "Eu não estava dormindo bem antes do exame."},
                {"en": "She had not (hadn't) been feeling well.", "pt": "Ela não estava se sentindo bem."},
                {"en": "They had not (hadn't) been paying attention.", "pt": "Eles não estavam prestando atenção."}
            ]
        },
        {
            "name": "Past Perfect Continuous: Questions",
            "usage": "Form: Had + subject + been + verb-ing?",
            "usage_pt": "Forma: Had + sujeito + been + verbo-ing?",
            "examples": [
                {"en": "Had you been waiting long?", "pt": "Você estava esperando há muito tempo?"},
                {"en": "Had she been working there before?", "pt": "Ela estava trabalhando lá antes?"},
                {"en": "Had they been expecting this outcome?", "pt": "Eles estavam esperando este resultado?"}
            ]
        },

        # Simple Future
        {
            "name": "Simple Future: I will work",
            "usage": "Usage: For predictions, promises, offers, and decisions made at the moment of speaking.",
            "usage_pt": "Uso: Para previsões, promessas, ofertas e decisões tomadas no momento da fala.",
            "examples": [
                {"en": "I will help you tomorrow.", "pt": "Eu vou te ajudar amanhã."},
                {"en": "She will probably arrive late.", "pt": "Ela provavelmente vai chegar atrasada."},
                {"en": "They will be here soon.", "pt": "Eles estarão aqui em breve."}
            ]
        },
        {
            "name": "Simple Future: Negatives",
            "usage": "Form: Subject + will + not + verb",
            "usage_pt": "Forma: Sujeito + will + not + verbo",
            "examples": [
                {"en": "I will not (won't) be available tomorrow.", "pt": "Eu não estarei disponível amanhã."},
                {"en": "She will not (won't) agree to these terms.", "pt": "Ela não vai concordar com estes termos."},
                {"en": "They will not (won't) finish on time.", "pt": "Eles não vão terminar a tempo."}
            ]
        },
        {
            "name": "Simple Future: Questions",
            "usage": "Form: Will + subject + verb?",
            "usage_pt": "Forma: Will + sujeito + verbo?",
            "examples": [
                {"en": "Will you attend the meeting?", "pt": "Você vai participar da reunião?"},
                {"en": "Will she join us for dinner?", "pt": "Ela vai se juntar a nós para o jantar?"},
                {"en": "Will they accept our offer?", "pt": "Eles vão aceitar nossa oferta?"}
            ]
        },

        # Future Continuous/Progressive
        {
            "name": "Future Continuous: I will be working",
            "usage": "Usage: For actions that will be in progress at a specific time in the future.",
            "usage_pt": "Uso: Para ações que estarão em andamento em um momento específico no futuro.",
            "examples": [
                {"en": "This time tomorrow, I will be flying to Paris.", "pt": "Amanhã a esta hora, eu estarei voando para Paris."},
                {"en": "She will be studying when you call.", "pt": "Ela estará estudando quando você ligar."},
                {"en": "They will be waiting for us when we arrive.", "pt": "Eles estarão esperando por nós quando chegarmos."}
            ]
        },
        {
            "name": "Future Continuous: Negatives",
            "usage": "Form: Subject + will + not + be + verb-ing",
            "usage_pt": "Forma: Sujeito + will + not + be + verbo-ing",
            "examples": [
                {"en": "I will not (won't) be working this weekend.", "pt": "Eu não estarei trabalhando neste fim de semana."},
                {"en": "She will not (won't) be attending the conference.", "pt": "Ela não estará participando da conferência."},
                {"en": "They will not (won't) be staying with us.", "pt": "Eles não estarão ficando conosco."}
            ]
        },
        {
            "name": "Future Continuous: Questions",
            "usage": "Form: Will + subject + be + verb-ing?",
            "usage_pt": "Forma: Will + sujeito + be + verbo-ing?",
            "examples": [
                {"en": "Will you be using the car tomorrow?", "pt": "Você estará usando o carro amanhã?"},
                {"en": "Will she be coming to the party?", "pt": "Ela estará vindo para a festa?"},
                {"en": "Will they be joining us for lunch?", "pt": "Eles estarão se juntando a nós para o almoço?"}
            ]
        },

        # Future Perfect
        {
            "name": "Future Perfect: I will have worked",
            "usage": "Usage: For actions that will be completed before a specific time in the future.",
            "usage_pt": "Uso: Para ações que serão concluídas antes de um momento específico no futuro.",
            "examples": [
                {"en": "By next month, I will have finished my degree.", "pt": "Até o próximo mês, eu terei terminado meu curso."},
                {"en": "She will have completed the project by Friday.", "pt": "Ela terá completado o projeto até sexta-feira."},
                {"en": "They will have moved into their new house by Christmas.", "pt": "Eles terão se mudado para a nova casa até o Natal."}
            ]
        },
        {
            "name": "Future Perfect: Negatives",
            "usage": "Form: Subject + will + not + have + past participle",
            "usage_pt": "Forma: Sujeito + will + not + have + particípio passado",
            "examples": [
                {"en": "I will not (won't) have read the book by then.", "pt": "Eu não terei lido o livro até lá."},
                {"en": "She will not (won't) have arrived by that time.", "pt": "Ela não terá chegado até aquela hora."},
                {"en": "They will not (won't) have made a decision before the deadline.", "pt": "Eles não terão tomado uma decisão antes do prazo."}
            ]
        },
        {
            "name": "Future Perfect: Questions",
            "usage": "Form: Will + subject + have + past participle?",
            "usage_pt": "Forma: Will + sujeito + have + particípio passado?",
            "examples": [
                {"en": "Will you have finished by tomorrow?", "pt": "Você terá terminado até amanhã?"},
                {"en": "Will she have prepared everything?", "pt": "Ela terá preparado tudo?"},
                {"en": "Will they have solved the problem by then?", "pt": "Eles terão resolvido o problema até lá?"}
            ]
        },

        # Future Perfect Continuous
        {
            "name": "Future Perfect Continuous: I will have been working",
            "usage": "Usage: For ongoing actions that will continue up to a specific time in the future, emphasizing duration.",
            "usage_pt": "Uso: Para ações contínuas que continuarão até um momento específico no futuro, enfatizando a duração.",
            "examples": [
                {"en": "By next week, I will have been working here for five years.", "pt": "Até a próxima semana, eu estarei trabalhando aqui há cinco anos."},
                {"en": "She will have been studying for six hours by the time she finishes.", "pt": "Ela estará estudando por seis horas quando terminar."},
                {"en": "They will have been traveling for two days when they arrive.", "pt": "Eles estarão viajando por dois dias quando chegarem."}
            ]
        },
        {
            "name": "Future Perfect Continuous: Negatives",
            "usage": "Form: Subject + will + not + have + been + verb-ing",
            "usage_pt": "Forma: Sujeito + will + not + have + been + verbo-ing",
            "examples": [
                {"en": "I will not (won't) have been waiting for more than an hour.", "pt": "Eu não estarei esperando por mais de uma hora."},
                {"en": "She will not (won't) have been teaching for very long.", "pt": "Ela não estará ensinando por muito tempo."},
                {"en": "They will not (won't) have been living there for much time.", "pt": "Eles não estarão morando lá por muito tempo."}
            ]
        },
        {
            "name": "Future Perfect Continuous: Questions",
            "usage": "Form: Will + subject + have + been + verb-ing?",
            "usage_pt": "Forma: Will + sujeito + have + been + verbo-ing?",
            "examples": [
                {"en": "Will you have been working all day?", "pt": "Você estará trabalhando o dia todo?"},
                {"en": "Will she have been practicing enough?", "pt": "Ela estará praticando o suficiente?"},
                {"en": "Will they have been searching for long?", "pt": "Eles estarão procurando por muito tempo?"}
            ]
        }
    ]

    # Create cards based on the structure
    cards = []
    for tense in tenses:
        tense_name = tense["name"]
        usage_pt = tense["usage_pt"]

        # For each example, create a flashcard
        for example in tense["examples"]:
            front = example["en"]
            back = f'(a) "{example["pt"]}"\n\n(b) {tense_name}\n\n(c) {usage_pt}'
            cards.append((front, back))

    return cards


def add_verbal_tenses_to_db(conn, model_id="1700000000001", deck_id=2):
    """
    Adds the Verbal Tenses sample deck to an Anki database.

    Args:
        conn: Open SQLite connection object
        model_id: Note model/template ID (default: "1700000000001")
        deck_id: Deck ID to add cards to (default: 2 = "Verbal Tenses" deck)

    Returns:
        int: Number of cards added

    Raises:
        Exception: If database insertion fails
    """
    cards_to_add = generate_verbal_tenses_flashcards()
    cursor = conn.cursor()

    current_time_sec = int(time.time())
    current_time_ms = int(current_time_sec * 1000)
    usn = -1  # Local changes

    for i, (front, back) in enumerate(cards_to_add):
        note_id = current_time_ms + i
        card_id = note_id + 1
        guid = str(uuid.uuid4())[:10]
        fields = f"{front}\x1f{back}"  # Fields separated by 0x1f
        checksum = sha1_checksum(front)

        # Insert Note
        cursor.execute("""
            INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (note_id, guid, model_id, current_time_sec, usn, "verbal_tenses", fields, front, int(checksum, 16) & 0xFFFFFFFF, 0, ""))

        # Insert Card (New card state)
        cursor.execute("""
            INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card_id, note_id, deck_id, 0, current_time_sec, usn,
            0,  # type = new
            0,  # queue = new
            note_id,  # due = note id for new cards
            0,  # ivl
            2500,  # factor (initial ease)
            0,  # reps
            0,  # lapses
            0,  # left (steps remaining)
            0,  # odue (original due)
            0,  # odid (original deck id)
            0,  # flags
            ""  # data
        ))

    conn.commit()
    return len(cards_to_add)
